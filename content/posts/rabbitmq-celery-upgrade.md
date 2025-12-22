+++
date = '2025-12-21T13:25:56+01:00'
draft = true
title = 'Upgrading RabbitMQ To v4.x Without Breaking Celery ETA Tasks'
+++

Upgrading to RabbitMQ v4 threatened to break our entire usage of Celery, more specifically tasks with ETAs.

At 8M messages/day with zero downtime tolerance, we needed a migration strategy that preserves delayed task execution while switching from classic to quorum queues.

<!--more-->

## Prerequisites
This post assumes familiarity with Celery task queues, RabbitMQ message brokers, and concepts like ETA/countdown tasks, global QoS, virtual hosts, and queue types. If you're comfortable with distributed task processing in Python, you're good to go.

## Context

At [Kraken](https://kraken.tech), we use [Celery](https://docs.celeryq.dev/) to offload long-running tasks to workers via [RabbitMQ](https://www.rabbitmq.com/) (v3.13.7.1). Our platform team needed to upgrade to RabbitMQ v4.2.2, which introduces breaking changes:

* [Global QoS removal](https://www.rabbitmq.com/blog/2021/08/21/4.0-deprecation-announcements#removal-of-global-qos) - ETA/countdown tasks now [block workers until execution time](https://docs.celeryq.dev/en/v5.6.0/getting-started/backends-and-brokers/rabbitmq.html#limitations)
* [Classic Queue Mirroring removal](https://www.rabbitmq.com/blog/2021/08/21/4.0-deprecation-announcements#removal-of-classic-queue-mirroring) - forced migration to [Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues)

## Challenges

**Can't switch queue types on the fly**: RabbitMQ doesn't let you change a queue's type after it's created. Normally you'd just delete the queue and recreate it with the new type, but that wasn't an option for us. We're pushing 8M messages/day across [many environments](https://engineering.kraken.tech/news/2025/02/07/how-we-ship.html), and our SLAs don't allow for any downtime.

**Workers would block indefinitely**: Without global QoS, any task with an ETA would block a worker until that ETA arrived, completely defeating the purpose of async processing. Fortunately, Celery has a feature called [Native Delayed Delivery](https://docs.celeryq.dev/en/v5.5.3/getting-started/backends-and-brokers/rabbitmq.html#native-delayed-delivery) that solves this—but it requires quorum queues bound to topic exchanges. Lucky for us, that's exactly what we needed to migrate to anyway.

## Solution

Our migration strategy:

1. Create a new [vhost](https://www.cloudamqp.com/blog/what-is-a-rabbitmq-vhost.html) (`qhost`), which will host quorum queues bound to topic exchanges
2. Configure application code to support both queue types via a feature flag
3. Transfer messages from old vhost (`chost`) to new vhost without losing ETA information
4. Decommission `chost`
5. [Rolling upgrade](https://www.rabbitmq.com/docs/rolling-upgrade) to RabbitMQ v4

### Phase 1: New Virtual Host

The first step was straightforward: create a new virtual host (`qhost`) to run alongside our existing one (`chost`). For us, this meant updating some infrastructure manifests to provision the new vhost. Not the most exciting part, but essential for what comes next—we needed both vhosts running simultaneously to avoid any downtime.

### Phase 2: Feature-Flagged Queue Configuration

Next, we needed to make our application code flexible enough to handle both the old and new queue configurations. We introduced a `USE_QUORUM_QUEUES` environment variable to control which type of queues to create:

```python
from kombu import Queue, Exchange
from django.conf import settings

def build_queue(queue_name: str) -> Queue:
    queue_type = "quorum" if settings.USE_QUORUM_QUEUES else "classic"
    exchange_type = "topic" if settings.USE_QUORUM_QUEUES else "direct"

    return Queue(
        name=queue_name,
        exchange=Exchange(queue_type, type=exchange_type),
        queue_arguments={"x-queue-type": queue_type}
    )

task_queues = [build_queue("first_queue"), ..., build_queue("last_queue")]
```

When we deployed this change, Kubernetes did its usual rolling update—pods gradually switched from `chost` to `qhost`. This meant we temporarily had some pods on the old vhost and some on the new one, which was totally fine. Any stragglers would get caught in Phase 3.

### Phase 3: Message Transfer with ETA Transformation

Here's where things got interesting. We needed to transfer potentially millions of messages from `chost` to `qhost` without losing any data or causing downtime.

At first glance, this sounds like a perfect job for RabbitMQ's [shovel](https://www.rabbitmq.com/docs/shovel) plugin, right? Just copy messages from one vhost to another. Unfortunately, a shovel copies messages as-is, including the `eta` header. That's exactly what we're trying to avoid—those headers would cause workers to block, bringing us right back to square one.

Instead, we had to transform messages during transfer. The idea was to replicate what [Celery does internally](https://github.com/celery/celery/blob/0527296acb1f1790788301d4395ba6d5ce2a9704/celery/app/base.py#L854-L876) when Native Delayed Delivery is enabled: extract the ETA header, calculate the appropriate delay-based routing key, and route to the right exchange. If you want to understand how this works under the hood, [this guide](https://docs.particular.net/transports/rabbitmq/delayed-delivery) explains the mechanics well.

Here's the core logic (simplified for clarity):

{{< code python >}}
import pika
from kombu.transport import native_delayed_delivery as kombu_utils

def get_routing_details(method, properties, queue_name):
    target_exchange_name = method.exchange or queue_name
    target_routing_key = method.routing_key or queue_name

    eta_str = str(properties.headers.pop("eta", ""))
    countdown_in_seconds = compute_countdown(eta_str)

    if countdown_in_seconds and countdown_in_seconds > 0:
        target_routing_key = kombu_utils.calculate_routing_key(int(countdown_in_seconds), target_routing_key)
        target_exchange_name = "celery_delayed_27"

    return target_routing_key, target_exchange_name

chost_connection_string = read_from_env("CHOST_CONNECTION_STRING")
qhost_connection_string = read_from_env("QHOST_CONNECTION_STRING")

source_channel = pika.BlockingConnection(pika.URLParameters(chost_connection_string)).channel()
dest_channel = pika.BlockingConnection(pika.URLParameters("amqps://user:pwd@host:port/qhost")).channel()

for method, properties, body in source_channel.consume("target_queue"):
    try:
        routing_key, exchange = get_routing_details(method, properties, "target_queue")
        dest_channel.basic_publish(exchange=exchange, routing_key=routing_key,
                                          body=body, properties=properties)
        source_conn.channel().basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        source_conn.channel().basic_nack(delivery_tag=method.delivery_tag, requeue=True)
{{< /code >}}


#### Some notes on the shoveling part:
* The above is pseudocode to illustrate the concept. Our production version uses `aio_pika` for async I/O (to avoid blocking), multiprocessing to handle high throughput, message backups for disaster recovery, and extensive logging to track everything.
* The script was deployed to run as a daemon, and would only work if `USE_QUORUM_QUEUES` was set to `True`.
* More mechanics were in place to determine if there were any messages to transfer in the first place, do transfers in batches, etc.


### Phase 4 & 5: Cleanup and Upgrade

Once all messages were safely transferred to `qhost`, our platform team took over for the final steps. They deleted the `chost` virtual host (which removed all the classic queues that are incompatible with v4), and then performed a [rolling upgrade](https://www.rabbitmq.com/docs/rolling-upgrade) to RabbitMQ v4.2.2.

And that was it! We successfully migrated from RabbitMQ v3 to v4 with zero downtime, while preserving ETA task behavior and handling 8M messages/day across all our environments.
