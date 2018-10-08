/* codegen.h */

/* AUTOMATICALLY GENERATED CODE: DO NOT EDIT DIRECTLY */

#include "min.h"
#include <stdint.h>

/* Update bit bytes for frames */
extern uint8_t min_f1_update_byte_0;
extern uint8_t min_f3_update_byte_0;
extern uint8_t min_f7_update_byte_0;

/* Frame sending period counters */
extern uint8_t min_f3_period_counter;
extern uint8_t min_f5_period_counter;
extern uint8_t min_f6_period_counter;

/* Prototypes for raw frame queueing functions */
void min_queue_frame_f5(uint8_t buf[], uint8_t control); /* Raw frame */
void min_queue_frame_f6(uint8_t buf[], uint8_t control); /* Raw frame */

/* Prototypes for unpacking raw frames; these are callbacks to user-provided functions */
void min_unpack_frame_f8(uint8_t buf[], uint8_t control); /* Raw frame; user-provided function */

/* Signal variables declarations (both input and output) */
extern uint8_t min_s1_var;
extern uint16_t min_s2_var;
extern uint32_t min_s3_var;
extern uint32_t min_i1_var;
extern uint32_t min_s4_var;
extern int16_t min_s5_var;
extern uint8_t min_s6_var;

/* Prototype for sending force transmit signals */

/* Inline macros for sending normal signals */
#define set_i1(n) ((min_i1_var) = (n),\
            min_f3_update_byte_0 |= 2U)
#define set_s4(n) ((min_s4_var) = (n),\
            min_f7_update_byte_0 |= 1U)
#define set_s5(n) ((min_s5_var) = (n),\
            min_f7_update_byte_0 |= 2U)
#define set_s6(n) ((min_s6_var) = (n),\
            min_f7_update_byte_0 |= 4U)

/* Received signal macros */
#define get_s1()       (min_s1_var)
#define get_s2()       (min_s2_var)
#define get_s3()       (min_s3_var)

/* Update bit testing for received signals */
#define updated_s1()   (min_f1_update_byte_0 & 1)

/* Clear update bit of received signal */
#define clear_updated_s1()    (min_f1_update_byte_0 &= ~1)

void min_input(void);
void min_output(void);
void min_initialize(void);
