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

The platform team wanted to perform an update of the RabbitMQ version we had to the latest 4.2.2, and all v4.x version 
come with these major changes:

* [Removal of global QoS](https://www.rabbitmq.com/blog/2021/08/21/4.0-deprecation-announcements#removal-of-global-qos)
* [Removal of Classic Queue mirroring](https://www.rabbitmq.com/blog/2021/08/21/4.0-deprecation-announcements#removal-of-classic-queue-mirroring)

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
* That kinda defeats the purpose of async processing
* ETAs can be quite long, so one task can hog and block all the rest.

## Solution

Luckily, 