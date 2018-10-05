#define ISMEGA 0

//#define NO_TRANSPORT_PROTOCOL
#if ISMEGA
//#define MIN_DEBUG_PRINTING
#endif

#include "min.h"
#include "min.c"

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

}
void min_tx_finished(uint8_t port)
{

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
  vsnprintf(dbgbuf,100,msg,args);
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
  min_queue_frame(&ctx, ++min_id, min_payload, len_payload);
}

/*** Handle Serial Data coming in ***/
void serialEvent()
{
  buflen = Serial.readBytes(serialBuf, Serial.available());
#if ISMEGA
  Serial1.print("incoming Serialbuf: ");
  Serial1.println(serialBuf);
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

void setup() {
#if ISMEGA
  Serial1.begin(115200);
  while (!Serial1);
#endif
  Serial.begin(115200);
  while (!Serial);
  pinMode(13, OUTPUT);

  min_init_context(&ctx, 0);
}

void loop() {
  // make sure MIN protocol runs
  min_poll(&ctx, serialBuf, buflen);
  buflen = 0;
  //
  
  static char msg[18] = "Toggled LED ##:";
  static byte n = 0;

  uint32_t now = millis();
  if (now - cTime > TOGGLETIME) {
    cTime = now;
    digitalWrite(13, !digitalRead(13));
    sprintf(msg + 15, "%3d", ++n);
    //min_send_frame(&ctx, 17, msg, 16);
    //min_send_frame(&ctx, 0x33,(uint8_t *) &now, 4);
    if (!min_queue_frame(&ctx, 17, msg, 18))
#if ISMEGA
      Serial1.println("couldn't queue id17");
#else
      min_send_frame(&ctx, 32, "couldn't queue id17", 19);
#endif
    if (!min_queue_frame(&ctx, 0x33, (uint8_t *) &now, 4))
#if ISMEGA
      Serial1.println("couldn't queue id0x33");
#else
      min_send_frame(&ctx, 32, "couldn't queue id0x33", 21);
#endif

#if ISMEGA
    for (int j = 0; j < 4; ++j) {
      Serial1.print(*((uint8_t *)&now + j), HEX);
      if (j < 3)
        Serial1.print("-");
    }
    Serial1.print("   =   ");
    Serial1.println(now);
#endif
  }
}
