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
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "../Comm.h"

/** frame length */
#define MAX_PAYLOAD (80)


/**
 * Class, that implements a byte wise frame that is interchanged by connection. The frame has an id and a payload
 * for the specific data. The data is stored as an byte array. It implements all functions to store and unpack
 * the data to and from byte wise array. The id represents the identification of the frame.
 */
class Frame {
public:
	struct _data {
		unsigned char id;
		unsigned char payload[MAX_PAYLOAD];
	} data;

	Frame(unsigned char id) {
		data.id = id;
		cCursor = 0;
	}

	Frame() {
		cCursor = 0;
	}

    /** pack value into Frame
     *
     * use `pack<typename>(value)` to be explicit
     **/
	template<typename T>
	void pack(T value) {
		const unsigned int sz = sizeof(T);
		assert(cCursor + sz < MAX_PAYLOAD);
		memcpy(&data.payload[cCursor], &value, sz);
		cCursor += sz;
	}

	/** unpack into value from Frame
     *
     * use `unPack<typename>(location)` to be explicit
     */
	template<typename T>
	void unPack(T &value) {
		const unsigned int sz = sizeof(T);
		assert(cCursor + sz < MAX_PAYLOAD);
		memcpy(&value, &data.payload[cCursor], sz);
		cCursor += sz;
	}

private:
	unsigned char cCursor;
};

#endif //SERVER_FRAME_H
