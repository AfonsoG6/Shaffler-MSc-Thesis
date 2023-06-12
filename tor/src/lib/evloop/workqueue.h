/* Copyright (c) 2013-2019, The Tor Project, Inc. */
/* See LICENSE for licensing information */

/**
 * \file workqueue.h
 * \brief Header for workqueue.c
 **/

#ifndef TOR_WORKQUEUE_H
#define TOR_WORKQUEUE_H

#include <event.h>

#include "lib/cc/torint.h"
#include "lib/thread/threads.h"

/** A replyqueue is used to tell the main thread about the outcome of
 * work that we queued for the workers. */
typedef struct replyqueue_s replyqueue_t;
/** A thread-pool manages starting threads and passing work to them. */
typedef struct threadpool_s threadpool_t;
/** A workqueue entry represents a request that has been passed to a thread
 * pool. */
typedef struct workqueue_entry_s workqueue_entry_t;

/** Possible return value from a work function: */
typedef enum workqueue_reply_t {
  WQ_RPL_REPLY = 0, /** indicates success */
  WQ_RPL_ERROR = 1, /** indicates fatal error */
  WQ_RPL_SHUTDOWN = 2, /** indicates thread is shutting down */
} workqueue_reply_t;

/** Possible priorities for work.  Lower numeric values are more important. */
typedef enum workqueue_priority_t {
  WQ_PRI_HIGH = 0,
  WQ_PRI_MED  = 1,
  WQ_PRI_LOW  = 2,
} workqueue_priority_t;

workqueue_entry_t *threadpool_queue_work_priority(threadpool_t *pool,
                                    workqueue_priority_t prio,
                                    workqueue_reply_t (*fn)(void *,
                                                            void *),
                                    void (*reply_fn)(void *, workqueue_reply_t),
                                    replyqueue_t *reply_queue,
                                    void *arg);

workqueue_entry_t *threadpool_queue_work(threadpool_t *pool,
                                         workqueue_reply_t (*fn)(void *,
                                                                 void *),
                                         void (*reply_fn)(void *, workqueue_reply_t),
                                         replyqueue_t *reply_queue,
                                         void *arg);

int threadpool_queue_update(threadpool_t *pool,
                            void *(*dup_fn)(void *),
                            workqueue_reply_t (*fn)(void *, void *),
                            void (*free_fn)(void *),
                            void *arg);
void *workqueue_entry_cancel(workqueue_entry_t *pending_work);
threadpool_t *threadpool_new(int n_threads,
                             void *(*new_thread_state_fn)(void*),
                             void (*free_thread_state_fn)(void*),
                             void *arg,
                             tor_thread_t *(*thread_spawn_fn)
                                           (void (*func)(void *),
                                            void *data));
void threadpool_shutdown(threadpool_t* pool);
threadpool_t *replyqueue_get_threadpool(replyqueue_t *rq);

replyqueue_t *replyqueue_new(uint32_t alertsocks_flags, threadpool_t *pool);
void replyqueue_process(replyqueue_t *queue);

int replyqueue_register_reply_event(replyqueue_t *reply_queue,
                                    struct event_base *base);
void threadpool_set_reply_cb(threadpool_t *tp,
                             void (*cb)(threadpool_t *, replyqueue_t *));

#endif /* !defined(TOR_WORKQUEUE_H) */
