/** @file define.h
 *
 */

#include <math.h>

#ifndef DEFINE_H
#define DEFINE_H

/**
 * @defgroup TRANSPORT Transport
 * Transport defines
 *
 * @{
 */
/** maximum payload per transport frame */
#define TRANSPORT_MAX_PAYLOAD           80U
/** transport tcp server port */
#define TRANSPORT_TCP_PORT              50007
/** frame length for doubles */
#define TRANSPORT_FRAME_LEN_DOUBLE      (TRANSPORT_MAX_PAYLOAD / sizeof(double))
/** @} */

#endif //DEFINE_H