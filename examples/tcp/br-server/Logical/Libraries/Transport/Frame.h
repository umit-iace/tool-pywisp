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

#include "../Comm.h"

/**
 * Class, that implements a byte wise frame that is interchanged by connection. The frame has an id and a payload
 * for the specific data. The data is stored as an byte array. It implements all functions to store and unpack
 * the data to and from byte wise array. The id represents the identification of the frame.
 */
class Frame {

public:
	struct _data {
		unsigned char id;
		unsigned char payload[80];
	} data;

	Frame(unsigned char id) {
		data.id = id;
		cCursor = 0;
	}

	Frame() {
		cCursor = 0;
	}

    /**
     * Adds a double value to payload
     * @param dValue value that is packed in payload
     */
	void pack(double dValue) {
		uPack.dVar = dValue;
		for (int i = 0; i < 8; ++i)
			data.payload[cCursor + i] = uPack.cVar[7 - i];

		cCursor += 8;
	};

    /**
     * Adds an unsigned long value to payload
     * @param lValue value that is packed in payload
     */
	void pack(unsigned long lValue) {
		data.payload[cCursor + 0] = (unsigned char) ((lValue & 0xff000000UL) >> 24);
		data.payload[cCursor + 1] = (unsigned char) ((lValue & 0x00ff0000UL) >> 16);
		data.payload[cCursor + 2] = (unsigned char) ((lValue & 0x0000ff00UL) >> 8);
		data.payload[cCursor + 3] = (unsigned char) (lValue & 0x000000ffUL);

		cCursor += 4;
	};

    /**
     * Adds a float value to payload
     * @param fValue value that is packed in payload
     */
	void pack(float fValue) {
		uPack.fVar1 = fValue;
		for (int i = 0; i < 4; ++i)
			data.payload[cCursor + i] = uPack.cVar[7 - i];

		cCursor += 4;
	};

    /**
     * Adds an integer value to payload
     * @param iValue value that is packed in payload
     */
	void pack(int iValue) {
		data.payload[cCursor + 0] = (unsigned char) ((iValue & 0x0000ff00UL) >> 8);
		data.payload[cCursor + 1] = (unsigned char) (iValue & 0x000000ffUL);

		cCursor += 2;
	};

    /**
     * Adds an unsigned char value to payload
     * @param cValue value that is packed in payload
     */
	void pack(unsigned char cValue) {
		data.payload[cCursor + 0] = cValue;

		cCursor++;
	};

    /**
     * Return a double value from payload
     * @param dValue value with unpacked data
     */
	void unPack(double &dValue) {
		for (int i = 0; i < 8; ++i)
			uPack.cVar[7 - i] = data.payload[cCursor + i];
		dValue = uPack.dVar;

		cCursor += 8;
	};

    /**
     * Return an unsigned long value from payload
     * @param lValue value with unpacked data
     */
	void unPack(unsigned long &lValue) {
		lValue = ((uint32_t) (data.payload[cCursor + 0]) << 24) |
			((uint32_t) (data.payload[cCursor + 1]) << 16) |
			((uint32_t) (data.payload[cCursor + 2]) << 8) |
			(uint32_t) (data.payload[cCursor + 3]);

		cCursor += 4;
	};

    /**
     * Return a float value from payload
     * @param fValue value with unpacked data
     */
	void unPack(float &fValue) {
		for (int i = 0; i < 4; ++i)
			uPack.cVar[7 - i] = data.payload[cCursor + i];
		fValue = uPack.fVar1;

		cCursor += 4;
	};

    /**
     * Return an integer value from payload
     * @param iValue value with unpacked data
     */
	void unPack(int &iValue) {
		iValue = ((uint32_t) (data.payload[cCursor + 0]) << 8) |
			(uint32_t) (data.payload[cCursor + 1]);

		cCursor += 2;
	};
	
	/**
     * Return an integer value from payload
     * @param iValue value with unpacked data
     */
	void unPack(short &iValue) {
		iValue = ((uint32_t) (data.payload[cCursor + 0]) << 8) |
			(uint32_t) (data.payload[cCursor + 1]);

		cCursor += 2;
	};

    /**
     * Return an unsigned char value from payload
     * @param cValue value with unpacked data
     */
	void unPack(unsigned char &cValue) {
		cValue = data.payload[cCursor + 0];

		cCursor++;
	};

    /**
     * Return a bool value from payload
     * @param bValue value with unpacked data
     */
	void unPack(bool &bValue) {
		bValue = data.payload[cCursor + 0];

		cCursor++;
	};

private:
	unsigned char cCursor;

	union {
		double dVar;
		struct {
			float fVar2;
			float fVar1;
		};
		unsigned char cVar[8];
	} uPack;

};

#endif //SERVER_FRAME_H
