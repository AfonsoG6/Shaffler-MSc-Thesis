#ifndef MAINLOOP_THROUGHPUT_LOG_H
#define MAINLOOP_THROUGHPUT_LOG_H

#include "lib/time/compat_time.h"

// the main thread should run the following before any threads have been
// created
void init_throughput_logging(int num_threads);
// the main thread should run the following after all threads have completed
void destroy_throughput_logging(void);

// each thread should run the following
void init_thread_throughput_logging(int thread_id);
void destroy_thread_throughput_logging(void);

// each thread should log the sent and received bytes with the following
void log_sent_bytes(uint32_t bytes, monotime_coarse_t *now);
void log_recv_bytes(uint32_t bytes, monotime_coarse_t *now);

// the file should be written to after all threads have finished but before
// calling 'destroy_throughput_logging()'
void write_throughput_log(char *file_name);

#endif
