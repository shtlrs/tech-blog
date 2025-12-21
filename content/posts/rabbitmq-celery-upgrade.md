+++
date = '2025-12-21T13:25:56+01:00'
draft = true
title = 'Migrating Celery tasks with ETAs'
+++

## Context

At [Kraken](https://kraken.tech), we use [Celery](https://docs.celeryq.dev/) heavily to dispatch long-running tasks 
to workers in order to not block the main request process for too long, which is a classic.

Our Celery publishers/workers publish/consume from [RabbitMQ](https://www.rabbitmq.com/), which was running on version 3.13.7.1.

```
Improve this section later
```

The platform team had to perform an update of the RabbitMQ version we had to the latest 4.2.2, and all v4.x version 
come with these major changes:

* [Removal of global QoS](https://www.rabbitmq.com/blog/2021/08/21/4.0-deprecation-announcements#removal-of-global-qos)
* [Removal of Classic Queue Mirroring](https://www.rabbitmq.com/blog/2021/08/21/4.0-deprecation-announcements#removal-of-classic-queue-mirroring)

## Problem
These changes come with great impact on Kraken:

* The removal of the global QoS meant that all tasks with an ETA/countdown will [block the worker until the ETA arrives](https://docs.celeryq.dev/en/v5.6.0/getting-started/backends-and-brokers/rabbitmq.html#limitations)
* We had to switch to [Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues) since we were using 
classic queues with [Classic Queue Mirroring](https://www.rabbitmq.com/docs/3.13/ha), which has been deprecated in 4.x versions

## Challenges

### Switching queues
RabbitMQ doesn't allow you to switch queue types on the fly. Once a Queue has been configured and declared, its configuration
can no longer change.

What you can do though is drop that queue, and re-create another one with the same name but with a different configuration.

This wasn't possible for us due to the amount of messages being published to those queues per day.
We have [a lot of environments](https://engineering.kraken.tech/news/2025/02/07/how-we-ship.html) deployed,
so the throughput changes based on that, but reaches around 8M messages per day in some.

Also, all of the above meant we'd have some sort of downtime window, which Kraken cannot afford due to certain SLAs we have to meet.

### Handling tasks with ETAs

We cannot afford to have our brokers block on tasks with etas because
* That defeats the purpose of async processing
* ETAs can be quite long, so one task can hog and block all the rest.

Luckily, Celery had something called [Native Delayed Delivery](https://docs.celeryq.dev/en/v5.5.3/getting-started/backends-and-brokers/rabbitmq.html#native-delayed-delivery)
implemented, which would allow us to preserve the same ETA behavior without blocking.

Being able to use this required that:
* All queues needed to be of type `quorum`, which is great because it already aligns with the queue type change I mentioned [previously](#switching-queues)
* All of these queues needed to be bound to `topic` exchanges


## Solution

Despite having figured out the `why`, we still have to determine the `how`.

Given all the aforementioned constraints, I have come up with the following multiphased plan: 

> These are just the headlines and I will give more specifics later.
> 
> I won't give all the specifics though for both brevity and confidentiality.

1. Creating a new [vhost (short for virtual host)](https://www.cloudamqp.com/blog/what-is-a-rabbitmq-vhost.html) on our deployed broker.
2. Create the queues required by our app in this new vhost, but with a new configuration: `quorum` queues, bound to `topic` exchanges.
3. Transfer all the messages in the old vhost to the newly created one, as fast as possible.
4. Decommissioning the old vhost.
5. Run a [rolling upgrade](https://www.rabbitmq.com/docs/rolling-upgrade) on the broker


### Key-words

To ease up remembering and cross-referencing things, here are the key-words to keep track of.

* `chost`: The old vhost that has all the `classic` queues.
* `qhost`: The new vhost that will contain all the `quorum` queues.

### Phase 1: Creating a new virtual host

This was quite an easy one. We just had to change some custom manifest file that would later on trigger a creation of a new vhost.

The details of this won't be covered here as they merely represent an operational detail.

The only important thing to remember is that after executing this, we will have both `chost` and `qhost` in our broker.

### Phase 2: Configuring and using `Quorum` queues

This one required a couple of code changes to be done, but is quite simple as well.

Usually, Celery will pick up all the queue definitions in the `task_queues` celery configuration variable, and create them automatically for us.

We don't let this Celery do this for us at Kraken, but to keep this simple, let's suppose that we haven't changed that behavior.

Whether we build `classic` or `quorum` queues and bind them to `direct` or `topic` changes was controlled
by a `USE_QUORUM_QUEUES` django setting, whose value comes from the `USE_QUORUM_QUEUES` env variable.

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


task_queues = [
    build_queue("first_queue"),
    ...,
    build_queue("last_queue"),
]

```

Once this code is shipped to production, we could control which instance in which environment we'd start
migrating by making the following environment variable changes:

* Set `USE_QUORUM_QUEUES` to `True`
* Change the `broker_url` celery setting to connect to `qhost` instead of `chost` so that we publish and consume tasks from `qhost`

```

Should i talk about pod rollout, and say we use k8s ? 
Should i mention that while pods were being rolled out, some messages would still go to `chost`, but tha's fine because they will be 
routed later ?

```

### Phase 3: Transferring the messages from `chost` to `qhost`
> If you want to easily understand the idea and the code snippets in this phase, 
> it's going to be very important to understand how `Native Delayed Delivery` works, so I suggest you have a read 
> at [this](https://docs.particular.net/transports/rabbitmq/delayed-delivery).


This was the most intricate phase because:
* We had to move as many tasks as we could in as little time as possible.
* We had to ensure that no tasks were dropped and no data was lost.
* We had to do this seamlessly with no downtime.


This sounds like a typical job for a [shovel](https://www.rabbitmq.com/docs/shovel), right ?

However, there's a big gotcha here, a shovel will take all messages and transfer them as is.

This is not something that would've worked for us, because it meant it'll also include the `eta` header in the message
that celery workers rely on to determine whether the task should run at dequeue time or not, which will make the workers block
because they no longer can store tasks in memory due to the removal of the global Qos I talked about 
[at the beginning](#problem), leading us back to square one.

The solution to this would be to imitate [how Celery does the enqueuing when the `Native Delayed Delivery` feature is enabled](https://github.com/celery/celery/blob/0527296acb1f1790788301d4395ba6d5ce2a9704/celery/app/base.py#L854-L876)
to shovel the tasks from `chost` to `qhost`

The basic idea is:
* Consume a message from `chost`.
* Pop the `eta` header, if it exists.
* Use it to compute the new `routing_key` and the `exchange` to use.
* Enqueue the task using the previously computed `routing_key` and `exchange`.


Here's some pseudocode that runs you through the necessary steps to transfer messages from one queue in `chost` to 
its "sister queue" in `qhost`:

{{< code python >}}

import pika
import datetime
from kombu.transport import native_delayed_delivery as kombu_utils


def get_routing_details(message, queue_name):
    # We default to the queue name because messages can be re-enqueued due to ack failures
    # This makes the message lose its exchange information or routing key, which should be the queue_name
    
    target_exchange_name = message.exchange or queue_name
    target_routing_key = message.routing_key or queue_name
    
    # eta_str will be an ISO datetime str    
    eta_str = str(message.headers.pop("eta", ""))

    countdown = compute_countdown(eta_str)

    if countdown and countdown > 0:
        # This is extracted from the celery framework itself
        # The relevant code block can be found here:
        # https://github.com/celery/celery/blob/f32b92f0e481601e9cc9f1212a4feced3f48e1a0/celery/app/base.py#L854-L876
        target_routing_key = kombu_utils.calculate_routing_key(int(countdown), target_routing_key)
        target_exchange_name = "celery_delayed_27"

    return target_routing_key, target_exchange_name

chost_url = "amqps://user:pwd@host:port/chost"
qhost_url = "amqps://user:pwd@host:port/qhost"

source_connection = pika.BlockingConnection(pika.URLParameters(chost_url))
destination_connection = pika.BlockingConnection(pika.URLParameters(qhost_url))

source_channel = source_connection.channel()
destination_channel = destination_connection.channel()

target_queue = "some_queue"

for method, properties, body in source_channel.consume(target_queue):
  try:
      routing_key, exchange_name = get_routing_details(method, target_queue)

      destination_channel.basic_publish(
          exchange=exchange_name,
          routing_key=routing_key,
          body=body,
          properties=properties
      )
      source_channel.basic_ack(delivery_tag=method.delivery_tag)
      
  except Exception:
      source_channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

{{< /code >}}

This is obviously just a snippet that I used to illustrate the idea. 

The code that runs in production is much more resilient, and includes things like:

* Using `aio_pika` to avoid blocking on message consumption and publishing.
* Using multiprocessing to squeeze even more performance out of the script and run this at scale. 
* Backing up each message being transferred, allowing us to restore them via another mechanism in case a disaster happens.
* Extensive and exhaustive logging in order to track what's happening in a detailed manner.


### Phase 4: Decommissioning the `chost` virtual host

This part being purely operational, it won't be covered in this document and was taken in charge by our platform team.

This step is necessary for the upgrade to happen since we cannot have any remaining queue of type `classic` in the broker
since they're no longer supported in v4.x versions.

However, it should be as simple as deleting the `chost` virtual host, which would take all of its classic queues away along with it.

### Phase 5: Running the rolling upgrade on the broker

Similarly to phase 4, this step was managed by the platform team and is mentioned in this document for exhaustiveness.


