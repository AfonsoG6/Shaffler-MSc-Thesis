
/* copyright (c) 2013-2015, The Tor Project, Inc. */
/* See LICENSE for licensing information */

/**
 * \file workqueue.c
 *
 * \brief Implements worker threads, queues of work for them, and mechanisms
 * for them to send answers back to the main thread.
 *
 * The main structure here is a threadpool_t : it manages a set of worker
 * threads, a queue of pending work, and a reply queue.  Every piece of work
 * is a workqueue_entry_t, containing data to process and a function to
 * process it with.
 *
 * The main thread informs the worker threads of pending work by using a
 * condition variable.  The workers inform the main process of completed work
 * by using an alert_sockets_t object, as implemented in net/alertsock.c.
 *
 * The main thread can also queue an "update" that will be handled by all the
 * workers.  This is useful for updating state that all the workers share.
 *
 * In Tor today, there is currently only one thread pool, used in cpuworker.c.
 */

#include "orconfig.h"
#include "lib/evloop/compat_libevent.h"
#include "lib/evloop/workqueue.h"

#include "lib/crypt_ops/crypto_rand.h"
#include "lib/intmath/weakrng.h"
#include "lib/log/ratelim.h"
#include "lib/log/log.h"
#include "lib/log/util_bug.h"
#include "lib/net/alertsock.h"
#include "lib/net/socket.h"

#include "ext/tor_queue.h"
#include <event2/event.h>
#include <string.h>

#define WORKQUEUE_PRIORITY_FIRST WQ_PRI_HIGH
#define WORKQUEUE_PRIORITY_LAST WQ_PRI_LOW
#define WORKQUEUE_N_PRIORITIES (((int) WORKQUEUE_PRIORITY_LAST)+1)

TOR_TAILQ_HEAD(work_tailq_t, workqueue_entry_s);
typedef struct work_tailq_t work_tailq_t;

struct threadpool_s {
  /** An array of pointers to workerthread_t: one for each running worker
   * thread. */
  struct workerthread_s **threads;

  /** Condition variable that we wait on when we have no work, and which
   * gets signaled when our queue becomes nonempty. */
  tor_cond_t condition;
  /** Queues of pending work that we have to do. The queue with priority
   * <b>p</b> is work[p]. */
  work_tailq_t work[WORKQUEUE_N_PRIORITIES];

  /** The current 'update generation' of the threadpool.  Any thread that is
   * at an earlier generation needs to run the update function. */
  unsigned generation;

  /** Flag to tell the worker threads to stop. */
  int shutdown;

  /** Function that should be run for updates on each thread. */
  workqueue_reply_t (*update_fn)(void *, void *);
  /** Function to free update arguments if they can't be run. */
  void (*free_update_arg_fn)(void *);
  /** Array of n_threads update arguments. */
  void **update_args;
  /** Callback that is run after a reply queue has processed work. */
  void (*reply_cb)(threadpool_t *, replyqueue_t *);

  /** Number of elements in threads. */
  int n_threads;
  /** Mutex to protect all the above fields. */
  tor_mutex_t lock;

  /** Functions used to allocate and free thread state. */
  void *(*new_thread_state_fn)(void*);
  void (*free_thread_state_fn)(void*);
  void *new_thread_state_arg;

  /** Function to start a thread. Should return a negative number on error. */
  tor_thread_t *(*thread_spawn_fn)(void (*func)(void *), void *data);
};

/** Used to put a workqueue_priority_t value into a bitfield. */
#define workqueue_priority_bitfield_t ENUM_BF(workqueue_priority_t)
/** Number of bits needed to hold all legal values of workqueue_priority_t */
#define WORKQUEUE_PRIORITY_BITS 2

struct workqueue_entry_s {
  /** The next workqueue_entry_t that's pending on the same thread or
   * reply queue. */
  TOR_TAILQ_ENTRY(workqueue_entry_s) next_work;
  /** The threadpool to which this workqueue_entry_t was assigned. This field
   * is set when the workqueue_entry_t is created, and won't be cleared until
   * after it's handled in the main thread. */
  struct threadpool_s *on_pool;
  /** True iff this entry is waiting for a worker to start processing it. */
  uint8_t pending;
  /** Priority of this entry. */
  workqueue_priority_bitfield_t priority : WORKQUEUE_PRIORITY_BITS;
  /** Function to run in the worker thread. */
  workqueue_reply_t (*fn)(void *state, void *arg);
  /** Function to run while processing the reply queue. */
  void (*reply_fn)(void *arg, workqueue_reply_t reply_status);
  /** Linked reply queue */
  replyqueue_t *reply_queue;
  /** Argument for the above functions. */
  void *arg;
  /** Reply status of the worker thread function after it has returned. */
  workqueue_reply_t reply_status;
};

struct replyqueue_s {
  /** Mutex to protect the answers field */
  tor_mutex_t lock;
  /** Doubly-linked list of answers that the reply queue needs to handle. */
  TOR_TAILQ_HEAD(, workqueue_entry_s) answers;

  /** Mechanism to wake up the main thread when it is receiving answers. */
  alert_sockets_t alert;
  /** Event to notice when another thread has sent a reply. */
  struct event *reply_event;

  /** The threadpool that uses this reply queue. */
  struct threadpool_s *pool;
};

/** A worker thread represents a single thread in a thread pool. */
typedef struct workerthread_s {
  /** Which thread it this?  In range 0..in_pool->n_threads-1 */
  int index;
  /** The tor thread object. */
  tor_thread_t* thread;
  /** The pool this thread is a part of. */
  struct threadpool_s *in_pool;
  /** User-supplied state field that we pass to the worker functions of each
   * work item. */
  void *state;
  /** The current update generation of this thread */
  unsigned generation;
  /** One over the probability of taking work from a lower-priority queue. */
  int32_t lower_priority_chance;
} workerthread_t;

static void queue_reply(replyqueue_t *queue, workqueue_entry_t *work);

/** Allocate and return a new workqueue_entry_t, set up to run the function
 * <b>fn</b> in the worker thread, and <b>reply_fn</b> in the main
 * thread. See threadpool_queue_work() for full documentation. */
static workqueue_entry_t *
workqueue_entry_new(workqueue_reply_t (*fn)(void*, void*),
                    void (*reply_fn)(void*, workqueue_reply_t),
                    replyqueue_t *reply_queue,
                    void *arg)
{
  workqueue_entry_t *ent = tor_malloc_zero(sizeof(workqueue_entry_t));
  ent->fn = fn;
  ent->reply_fn = reply_fn;
  ent->reply_queue = reply_queue;
  ent->arg = arg;
  ent->priority = WQ_PRI_HIGH;
  return ent;
}

#define workqueue_entry_free(ent) \
  FREE_AND_NULL(workqueue_entry_t, workqueue_entry_free_, (ent))

/**
 * Release all storage held in <b>ent</b>. Call only when <b>ent</b> is not on
 * any queue.
 */
static void
workqueue_entry_free_(workqueue_entry_t *ent)
{
  if (!ent)
    return;
  memset(ent, 0xf0, sizeof(*ent));
  tor_free(ent);
}

/**
 * Cancel a workqueue_entry_t that has been returned from
 * threadpool_queue_work.
 *
 * You must not call this function on any work whose reply function has been
 * executed in the main thread; that will cause undefined behavior (probably,
 * a crash).
 *
 * If the work is cancelled, this function return the argument passed to the
 * work function. It is the caller's responsibility to free this storage.
 *
 * This function will have no effect if the worker thread has already executed
 * or begun to execute the work item.  In that case, it will return NULL.
 */
void *
workqueue_entry_cancel(workqueue_entry_t *ent)
{
  int cancelled = 0;
  void *result = NULL;
  tor_mutex_acquire(&ent->on_pool->lock);
  workqueue_priority_t prio = ent->priority;
  if (ent->pending) {
    TOR_TAILQ_REMOVE(&ent->on_pool->work[prio], ent, next_work);
    cancelled = 1;
    result = ent->arg;
  }
  tor_mutex_release(&ent->on_pool->lock);

  if (cancelled) {
    workqueue_entry_free(ent);
  }
  return result;
}

/**DOCDOC

   must hold lock */
static int
worker_thread_has_work(workerthread_t *thread)
{
  unsigned i;
  for (i = WORKQUEUE_PRIORITY_FIRST; i <= WORKQUEUE_PRIORITY_LAST; ++i) {
    if (!TOR_TAILQ_EMPTY(&thread->in_pool->work[i]))
        return 1;
  }
  return thread->generation != thread->in_pool->generation;
}

/** Extract the next workqueue_entry_t from the the thread's pool, removing
 * it from the relevant queues and marking it as non-pending.
 *
 * The caller must hold the lock. */
static workqueue_entry_t *
worker_thread_extract_next_work(workerthread_t *thread)
{
  threadpool_t *pool = thread->in_pool;
  work_tailq_t *queue = NULL, *this_queue;
  unsigned i;
  for (i = WORKQUEUE_PRIORITY_FIRST; i <= WORKQUEUE_PRIORITY_LAST; ++i) {
    this_queue = &pool->work[i];
    if (!TOR_TAILQ_EMPTY(this_queue)) {
      queue = this_queue;
      if (! crypto_fast_rng_one_in_n(get_thread_fast_rng(),
                                     thread->lower_priority_chance)) {
        /* Usually we'll just break now, so that we can get out of the loop
         * and use the queue where we found work. But with a small
         * probability, we'll keep looking for lower priority work, so that
         * we don't ignore our low-priority queues entirely. */
        break;
      }
    }
  }

  if (queue == NULL)
    return NULL;

  workqueue_entry_t *work = TOR_TAILQ_FIRST(queue);
  TOR_TAILQ_REMOVE(queue, work, next_work);
  work->pending = 0;
  return work;
}

/**
 * Main function for the worker thread.
 */
static void
worker_thread_main(void *thread_)
{
  workerthread_t *thread = thread_;
  threadpool_t *pool = thread->in_pool;
  workqueue_entry_t *work;
  workqueue_reply_t result;

  tor_mutex_acquire(&pool->lock);
  while (1) {
    /* lock must be held at this point. */
    while (worker_thread_has_work(thread)) {
      /* lock must be held at this point. */
      if (thread->in_pool->generation != thread->generation) {
        void *arg = thread->in_pool->update_args[thread->index];
        thread->in_pool->update_args[thread->index] = NULL;
        workqueue_reply_t (*update_fn)(void*,void*) =
            thread->in_pool->update_fn;
        thread->generation = thread->in_pool->generation;
        tor_mutex_release(&pool->lock);

        workqueue_reply_t r = update_fn(thread->state, arg);

        if (r != WQ_RPL_REPLY) {
          return;
        }

        tor_mutex_acquire(&pool->lock);
        continue;
      }
      work = worker_thread_extract_next_work(thread);
      if (BUG(work == NULL)) {
        break;
      }
      if (pool->shutdown) {
        /* If the pool wants to shutdown, we still need to reply so
           that the reply functions have a chance to free memory. */
        tor_mutex_release(&pool->lock);
        work->reply_status = WQ_RPL_SHUTDOWN;
        queue_reply(work->reply_queue, work);
        tor_mutex_acquire(&pool->lock);
      } else {
        tor_mutex_release(&pool->lock);

        /* We run the work function without holding the thread lock. This
         * is the main thread's first opportunity to give us more work. */
        result = work->fn(thread->state, work->arg);

        /* Queue the reply for the main thread. */
        work->reply_status = result;
        queue_reply(work->reply_queue, work);

        /* We may need to exit the thread. */
        if (result != WQ_RPL_REPLY) {
          return;
        }
        tor_mutex_acquire(&pool->lock);
      }
    }
    /* At this point the lock is held, and there is no work in this thread's
     * queue. */

    if (pool->shutdown) {
      tor_mutex_release(&pool->lock);
      return;
    }

    /* TODO: support an idle-function */

    /* Okay. Now, wait till somebody has work for us. */
    if (tor_cond_wait(&pool->condition, &pool->lock, NULL) < 0) {
      log_warn(LD_GENERAL, "Fail tor_cond_wait.");
    }
  }
}

/** Put a reply on the reply queue.  The reply must not currently be on
 * any thread's work queue. */
static void
queue_reply(replyqueue_t *queue, workqueue_entry_t *work)
{
  int was_empty;
  tor_mutex_acquire(&queue->lock);
  was_empty = TOR_TAILQ_EMPTY(&queue->answers);
  TOR_TAILQ_INSERT_TAIL(&queue->answers, work, next_work);
  tor_mutex_release(&queue->lock);

  if (was_empty) {
    if (queue->alert.alert_fn(queue->alert.write_fd) < 0) {
      /* XXXX complain! */
    }
  }
}

/** Allocate and start a new worker thread to use state object <b>state</b>. */
static workerthread_t *
workerthread_new(int32_t lower_priority_chance,
                 void *state, threadpool_t *pool)
{
  workerthread_t *thr = tor_malloc_zero(sizeof(workerthread_t));
  thr->state = state;
  thr->in_pool = pool;
  thr->lower_priority_chance = lower_priority_chance;

  tor_assert(pool->thread_spawn_fn != NULL);
  tor_thread_t* thread = pool->thread_spawn_fn(worker_thread_main, thr);
  if (thread == NULL) {
    //LCOV_EXCL_START
    tor_assert_nonfatal_unreached();
    log_err(LD_GENERAL, "Can't launch worker thread.");
    tor_free(thr);
    return NULL;
    //LCOV_EXCL_STOP
  }

  thr->thread = thread;

  return thr;
}

static void
workerthread_join(workerthread_t* thr)
{
  if (join_thread(thr->thread) != 0) {
    log_err(LD_GENERAL, "Could not join workerthread.");
  }
}

static void
workerthread_free(workerthread_t* thr)
{
  free_thread(thr->thread);
}

/**
 * Queue an item of work for a thread in a thread pool.  The function
 * <b>fn</b> will be run in a worker thread, and will receive as arguments the
 * thread's state object, and the provided object <b>arg</b>. It must return
 * one of WQ_RPL_REPLY, WQ_RPL_ERROR, or WQ_RPL_SHUTDOWN.
 *
 * Regardless of its return value, the function <b>reply_fn</b> will later be
 * run in the main thread when it invokes replyqueue_process(), and will
 * receive as its argument the same <b>arg</b> object.  It's the reply
 * function's responsibility to free the work object.
 *
 * On success, return a workqueue_entry_t object that can be passed to
 * workqueue_entry_cancel(). On failure, return NULL.
 *
 * Items are executed in a loose priority order -- each thread will usually
 * take from the queued work with the highest prioirity, but will occasionally
 * visit lower-priority queues to keep them from starving completely.
 *
 * Note that because of priorities and thread behavior, work items may not
 * be executed strictly in order.
 */
workqueue_entry_t *
threadpool_queue_work_priority(threadpool_t *pool,
                               workqueue_priority_t prio,
                               workqueue_reply_t (*fn)(void *, void *),
                               void (*reply_fn)(void *, workqueue_reply_t),
                               replyqueue_t *reply_queue,
                               void *arg)
{
  tor_assert(((int)prio) >= WORKQUEUE_PRIORITY_FIRST &&
             ((int)prio) <= WORKQUEUE_PRIORITY_LAST);

  tor_mutex_acquire(&pool->lock);

  if (pool->shutdown) {
    return NULL;
  }

  workqueue_entry_t *ent = workqueue_entry_new(fn, reply_fn, reply_queue, arg);
  ent->on_pool = pool;
  ent->pending = 1;
  ent->priority = prio;

  TOR_TAILQ_INSERT_TAIL(&pool->work[prio], ent, next_work);

  tor_cond_signal_one(&pool->condition);

  tor_mutex_release(&pool->lock);

  return ent;
}

/** As threadpool_queue_work_priority(), but assumes WQ_PRI_HIGH */
workqueue_entry_t *
threadpool_queue_work(threadpool_t *pool,
                      workqueue_reply_t (*fn)(void *, void *),
                      void (*reply_fn)(void *, workqueue_reply_t),
                      replyqueue_t *reply_queue,
                      void *arg)
{
  return threadpool_queue_work_priority(pool, WQ_PRI_HIGH, fn,
                                        reply_fn, reply_queue, arg);
}

/**
 * Queue a copy of a work item for every thread in a pool.  This can be used,
 * for example, to tell the threads to update some parameter in their states.
 *
 * Arguments are as for <b>threadpool_queue_work</b>, except that the
 * <b>arg</b> value is passed to <b>dup_fn</b> once per each thread to
 * make a copy of it.
 *
 * UPDATE FUNCTIONS MUST BE IDEMPOTENT.  We do not guarantee that every update
 * will be run.  If a new update is scheduled before the old update finishes
 * running, then the new will replace the old in any threads that haven't run
 * it yet.
 *
 * Return 0 on success, -1 on failure.
 */
int
threadpool_queue_update(threadpool_t *pool,
                         void *(*dup_fn)(void *),
                         workqueue_reply_t (*fn)(void *, void *),
                         void (*free_fn)(void *),
                         void *arg)
{
  int i, n_threads;
  void (*old_args_free_fn)(void *arg);
  void **old_args;
  void **new_args;

  tor_mutex_acquire(&pool->lock);

  if (pool->shutdown) {
    return -1;
  }

  n_threads = pool->n_threads;
  old_args = pool->update_args;
  old_args_free_fn = pool->free_update_arg_fn;

  new_args = tor_calloc(n_threads, sizeof(void*));
  for (i = 0; i < n_threads; ++i) {
    if (dup_fn)
      new_args[i] = dup_fn(arg);
    else
      new_args[i] = arg;
  }

  pool->update_args = new_args;
  pool->free_update_arg_fn = free_fn;
  pool->update_fn = fn;
  ++pool->generation;

  tor_cond_signal_all(&pool->condition);

  tor_mutex_release(&pool->lock);

  if (old_args) {
    for (i = 0; i < n_threads; ++i) {
      if (old_args[i] && old_args_free_fn)
        old_args_free_fn(old_args[i]);
    }
    tor_free(old_args);
  }

  return 0;
}

/** Don't have more than this many threads per pool. */
#define MAX_THREADS 1024

/** For half of our threads, choose lower priority queues with probability
 * 1/N for each of these values. Both are chosen somewhat arbitrarily.  If
 * CHANCE_PERMISSIVE is too low, then we have a risk of low-priority tasks
 * stalling forever.  If it's too high, we have a risk of low-priority tasks
 * grabbing half of the threads. */
#define CHANCE_PERMISSIVE 37
#define CHANCE_STRICT INT32_MAX

/** Launch threads until we have <b>n</b>. */
static int
threadpool_start_threads(threadpool_t *pool, int n)
{
  if (BUG(n < 0))
    return -1; // LCOV_EXCL_LINE
  if (n > MAX_THREADS)
    n = MAX_THREADS;

  tor_mutex_acquire(&pool->lock);

  if (pool->n_threads < n)
    pool->threads = tor_reallocarray(pool->threads,
                                     sizeof(workerthread_t*), n);

  while (pool->n_threads < n) {
    /* For half of our threads, we'll choose lower priorities permissively;
     * for the other half, we'll stick more strictly to higher priorities.
     * This keeps slow low-priority tasks from taking over completely. */
    int32_t chance = (pool->n_threads & 1) ? CHANCE_STRICT : CHANCE_PERMISSIVE;

    void *state = pool->new_thread_state_fn(pool->new_thread_state_arg);
    workerthread_t *thr = workerthread_new(chance,
                                           state, pool);

    if (!thr) {
      //LCOV_EXCL_START
      tor_assert_nonfatal_unreached();
      pool->free_thread_state_fn(state);
      tor_mutex_release(&pool->lock);
      return -1;
      //LCOV_EXCL_STOP
    }
    thr->index = pool->n_threads;
    pool->threads[pool->n_threads++] = thr;
  }
  tor_mutex_release(&pool->lock);

  return 0;
}

/**
 * Construct a new thread pool with <b>n</b> worker threads. The threads'
 * states will be constructed with the <b>new_thread_state_fn</b> call,
 * receiving <b>arg</b> as its argument.  When the threads close, they
 * will call <b>free_thread_state_fn</b> on their states.
 */
threadpool_t *
threadpool_new(int n_threads,
               void *(*new_thread_state_fn)(void*),
               void (*free_thread_state_fn)(void*),
               void *arg,
               tor_thread_t *(*thread_spawn_fn)(void (*func)(void *), void *data))
{
  threadpool_t *pool;
  pool = tor_malloc_zero(sizeof(threadpool_t));
  tor_mutex_init_nonrecursive(&pool->lock);
  tor_cond_init(&pool->condition);
  unsigned i;
  for (i = WORKQUEUE_PRIORITY_FIRST; i <= WORKQUEUE_PRIORITY_LAST; ++i) {
    TOR_TAILQ_INIT(&pool->work[i]);
  }

  pool->new_thread_state_fn = new_thread_state_fn;
  pool->new_thread_state_arg = arg;
  pool->free_thread_state_fn = free_thread_state_fn;
  pool->thread_spawn_fn = thread_spawn_fn;

  if (threadpool_start_threads(pool, n_threads) < 0) {
    //LCOV_EXCL_START
    tor_assert_nonfatal_unreached();
    tor_cond_uninit(&pool->condition);
    tor_mutex_uninit(&pool->lock);
    tor_free(pool);
    return NULL;
    //LCOV_EXCL_STOP
  }

  return pool;
}

void
threadpool_shutdown(threadpool_t* pool)
{
  tor_assert(pool != NULL);
  tor_mutex_acquire(&pool->lock);
  pool->shutdown = 1;
  tor_cond_signal_all(&pool->condition);

  for (int i=0; i<pool->n_threads; i++) {
    workerthread_t *thread = pool->threads[i];
    tor_mutex_release(&pool->lock);
    workerthread_join(thread);
    tor_mutex_acquire(&pool->lock);
  }

  for (int i=0; i<pool->n_threads; i++) {
    workerthread_free(pool->threads[i]);
    pool->free_thread_state_fn(pool->threads[i]->state);
  }

  tor_mutex_release(&pool->lock);
}

/** Return the thread pool associated with a given reply queue. */
threadpool_t *
replyqueue_get_threadpool(replyqueue_t *rq)
{
  return rq->pool;
}

/** Allocate a new reply queue.  Reply queues are used to pass results from
 * worker threads to the main thread.  Since the main thread is running an
 * IO-centric event loop, it needs to get woken up with means other than a
 * condition variable. */
replyqueue_t *
replyqueue_new(uint32_t alertsocks_flags, threadpool_t *pool)
{
  replyqueue_t *rq;

  rq = tor_malloc_zero(sizeof(replyqueue_t));
  if (alert_sockets_create(&rq->alert, alertsocks_flags) < 0) {
    //LCOV_EXCL_START
    tor_free(rq);
    return NULL;
    //LCOV_EXCL_STOP
  }

  rq->pool = pool;

  tor_mutex_init(&rq->lock);
  TOR_TAILQ_INIT(&rq->answers);

  return rq;
}

/** Internal: Run from the libevent mainloop when there is work to handle in
 * the reply queue handler. */
static void
reply_event_cb(evutil_socket_t sock, short events, void *arg)
{
  replyqueue_t *reply_queue = arg;
  (void) sock;
  (void) events;
  replyqueue_process(reply_queue);
  if (reply_queue->pool && reply_queue->pool->reply_cb)
    reply_queue->pool->reply_cb(reply_queue->pool, reply_queue);
}

/** Register the reply queue with the given libevent mainloop. Return 0
 * on success, -1 on failure.
 */
int
replyqueue_register_reply_event(replyqueue_t *reply_queue,
                                struct event_base *base)
{
  if (reply_queue->reply_event) {
    tor_event_free(reply_queue->reply_event);
  }
  reply_queue->reply_event = tor_event_new(base,
                                           reply_queue->alert.read_fd,
                                           EV_READ|EV_PERSIST,
                                           reply_event_cb,
                                           reply_queue);
  tor_assert(reply_queue->reply_event);
  return event_add(reply_queue->reply_event, NULL);
}

/** The given callback is run after each time there is work to process
 * from a reply queue. Return 0 on success, -1 on failure.
 */
void
threadpool_set_reply_cb(threadpool_t *tp,
                        void (*cb)(threadpool_t *tp, replyqueue_t *rq))
{
  tp->reply_cb = cb;
}

/**
 * Process all pending replies on a reply queue. The main thread should call
 * this function every time the socket returned by replyqueue_get_socket() is
 * readable.
 */
void
replyqueue_process(replyqueue_t *queue)
{
  int r = queue->alert.drain_fn(queue->alert.read_fd);
  if (r < 0) {
    //LCOV_EXCL_START
    static ratelim_t warn_limit = RATELIM_INIT(7200);
    log_fn_ratelim(&warn_limit, LOG_WARN, LD_GENERAL,
                 "Failure from drain_fd: %s",
                   tor_socket_strerror(-r));
    //LCOV_EXCL_STOP
  }

  tor_mutex_acquire(&queue->lock);
  while (!TOR_TAILQ_EMPTY(&queue->answers)) {
    /* lock must be held at this point.*/
    workqueue_entry_t *work = TOR_TAILQ_FIRST(&queue->answers);
    TOR_TAILQ_REMOVE(&queue->answers, work, next_work);
    tor_mutex_release(&queue->lock);
    work->on_pool = NULL;

    work->reply_fn(work->arg, work->reply_status);
    workqueue_entry_free(work);

    tor_mutex_acquire(&queue->lock);
  }

  tor_mutex_release(&queue->lock);
}
