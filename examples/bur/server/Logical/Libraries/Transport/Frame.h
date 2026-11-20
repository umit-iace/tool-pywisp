/** @file Frame.h
 *
 */
#ifndef FRAME_H
#define FRAME_H

#include <bur/plctypes.h>
#ifdef _DEFAULT_INCLUDES
#include <AsDefault.h>
#endif
#include <stdint.h>
#include <string.h>

/** payload of a frame [B], pyWisp's TcpConnection sends and receives 1 byte id + MAX_PAYLOAD bytes */
#define MAX_PAYLOAD (80)

/**
 * @class Frame
 * @brief Class that implements a byte wise frame that is interchanged by connection. The frame has an id and a payload
 * for the specific data. The data is stored as an byte array. It implements all functions to store and unpack
 * the data to and from byte wise array, little endian (struct format '<' in pyWisp) independent of the CPU.
 * The id represents the identification of the frame.
 * Values that do not fit into the payload are not packed (pack) or left unchanged (unPack).
 */
class Frame {

	public:
	struct _data {
		unsigned char id;
		unsigned char payload[MAX_PAYLOAD];
	} data;

	Frame(unsigned char id = 0) {
		data.id = id;
		memset(data.payload, 0, sizeof(data.payload));
		cCursor = 0;
	}

	/** Adds a double value (8 bytes) to the payload */
	void pack(double dValue) {
		uint64_t v;
		memcpy(&v, &dValue, sizeof(v));
		packBytes(v, 8);
	};

	/** Adds an unsigned long value (4 bytes) to the payload */
	void pack(unsigned long lValue) {
		packBytes(lValue, 4);
	};

	/** Adds a float value (4 bytes) to the payload */
	void pack(float fValue) {
		uint32_t v;
		memcpy(&v, &fValue, sizeof(v));
		packBytes(v, 4);
	};

	/** Adds a 2 byte integer value to the payload */
	void pack(short iValue) {
		packBytes((uint16_t)iValue, 2);
	};

	/** Adds an unsigned char value to the payload */
	void pack(unsigned char cValue) {
		packBytes(cValue, 1);
	};

	/** Reads a double value (8 bytes) from the payload */
	void unPack(double &dValue) {
		uint64_t v;
		if (unPackBytes(v, 8))
			memcpy(&dValue, &v, sizeof(v));
	};

	/** Reads an unsigned long value (4 bytes) from the payload */
	void unPack(unsigned long &lValue) {
		uint64_t v;
		if (unPackBytes(v, 4))
			lValue = (unsigned long)v;
	};

	/** Reads a float value (4 bytes) from the payload */
	void unPack(float &fValue) {
		uint64_t v;
		if (unPackBytes(v, 4)) {
			uint32_t v32 = (uint32_t)v;
			memcpy(&fValue, &v32, sizeof(v32));
		}
	};

	/** Reads a 2 byte integer value from the payload */
	void unPack(short &iValue) {
		uint64_t v;
		if (unPackBytes(v, 2))
			iValue = (short)(uint16_t)v;
	};

	/** Reads a 2 byte unsigned integer value from the payload */
	void unPack(unsigned short &iValue) {
		uint64_t v;
		if (unPackBytes(v, 2))
			iValue = (unsigned short)v;
	};

	/** Reads an unsigned char value from the payload */
	void unPack(unsigned char &cValue) {
		uint64_t v;
		if (unPackBytes(v, 1))
			cValue = (unsigned char)v;
	};

	private:
	unsigned char cCursor;

	/** packs the lowest n bytes of v little endian */
	void packBytes(uint64_t v, unsigned int n) {
		if (cCursor + n > MAX_PAYLOAD)
			return;
		for (unsigned int i = 0; i < n; ++i)
			data.payload[cCursor + i] = (unsigned char)(v >> (8 * i));
		cCursor += n;
	}

	/** unpacks n bytes little endian, false if the payload is too short */
	bool unPackBytes(uint64_t &v, unsigned int n) {
		if (cCursor + n > MAX_PAYLOAD)
			return false;
		v = 0;
		for (unsigned int i = 0; i < n; ++i)
			v |= (uint64_t)data.payload[cCursor + i] << (8 * i);
		cCursor += n;
		return true;
	}
};

#endif //FRAME_H
