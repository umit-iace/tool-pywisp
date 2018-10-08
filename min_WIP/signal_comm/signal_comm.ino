#define ISMEGA 1

//#define NO_TRANSPORT_PROTOCOL
#if ISMEGA
#define MIN_DEBUG_PRINTING
#endif

extern "C" {
#include "min.h"
#include "gen.h"
}



#define BUFLEN (64)
struct min_context ctx;
uint8_t serialBuf[BUFLEN];
uint8_t buflen;

#define TOGGLETIME (2000)
uint32_t cTime = 0;

/*** MIN Callbacks ***/

uint16_t min_tx_space(uint8_t port)
{
  return Serial.availableForWrite();
}

void min_tx_byte(uint8_t port, uint8_t byte)
{
  Serial.write(&byte, 1);
}

void min_tx_start(uint8_t port)
{
  Serial1.print("started transmission -");

}
void min_tx_finished(uint8_t port)
{
  Serial1.println(" - end");
}

#ifdef TRANSPORT_PROTOCOL
uint32_t min_time_ms(void)
{
  return millis();
}
#endif

#ifdef MIN_DEBUG_PRINTING
void min_debug_print(const char *msg, ...)
{
  char dbgbuf[100];
  va_list args;
  va_start(args, msg);
  vsnprintf(dbgbuf, 100, msg, args);
  va_end(args);
  Serial1.print(dbgbuf);
}
#endif

void min_application_handler(uint8_t min_id, uint8_t *min_payload, uint8_t len_payload, uint8_t port)
{
#if ISMEGA
  Serial1.print("MIN frame ID: "); Serial1.print(min_id); Serial1.print(" at "); Serial1.println(millis());
  Serial1.print("payload: "); Serial1.write(min_payload, len_payload); Serial1.println();
#endif
  //min_queue_frame(&ctx, ++min_id, min_payload, len_payload);
  min_frame_received(min_payload, len_payload, min_id);
}

/*** Handle Serial Data coming in ***/
void serialEvent()
{
  buflen = Serial.readBytes(serialBuf, Serial.available());
#if ISMEGA
  Serial1.print("incoming Serialbuf: ");
  Serial1.write(serialBuf, buflen);
#endif
}

#if ISMEGA
void serialEvent1()
{
  char buf[50];
  int n = Serial1.readBytes(buf, 50);
  min_send_frame(&ctx, 15, buf, n);
  Serial1.println("Sent buffer through min");
}
#endif


////////////////////
////SIGNAL LAYER////
////////////////////

void min_tx_frame(uint8_t id, uint8_t payload[], uint8_t control)
{
  min_queue_frame(&ctx, id, payload, control);
}

uint8_t uart_receive_ready(void)
{
  return Serial.available();
}

void uart_receive(uint8_t *p, uint8_t n)
{
  Serial.readBytes(p, n);
}

void min_rx_byte(uint8_t byte)
{
  min_poll(&ctx, &byte, 1);
}

/* Callback */
void min_unpack_frame_f8(uint8_t buf[], uint8_t control)
{
#if ISMEGA
  Serial1.println("received f8");
#endif
}

//\\\\\\\\\\\\\\\\\\
//\\SIGNAL LAYER\\\\
//\\\\\\\\\\\\\\\\\\


void setup() {
#if ISMEGA
  Serial1.begin(115200);
  while (!Serial1);
#endif
  Serial.begin(115200);
  while (!Serial);
  pinMode(13, OUTPUT);

  min_init_context(&ctx, 0);
  min_initialize();
}

void loop() {

  min_input();
  min_output();
  uint32_t now = millis();
  if (now - cTime > TOGGLETIME) {
    cTime = now;
    if (updated_s1()) {
    Serial1.print("s1: ");
    Serial1.println(get_s1());
    }
    set_s4(now);
    set_s5(512);
    set_s6(0xff000000);
    digitalWrite(13, !digitalRead(13));
  }
}
