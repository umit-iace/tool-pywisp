# -*- coding: utf-8 -*-
import struct

import pytest

from pywisp.utils import packArrayToFrame


def unpack(frames, dataLenFloat, dataLenInt):
    f = 'f' if dataLenFloat == 4 else 'd'
    i = {1: 'B', 2: 'H', 4: 'I', 8: 'Q'}[dataLenInt]
    first = frames[0]['msg']
    n = (len(first) - dataLenInt) // dataLenFloat
    length, *values = struct.unpack(f'<{i}{n}{f}', first)
    for fr in frames[1:]:
        values += struct.unpack(f'<{len(fr["msg"]) // dataLenFloat}{f}', fr['msg'])
    return length, values


@pytest.mark.parametrize("frameLen, dataLenFloat, dataLenInt", [
    (80, 4, 4), (80, 4, 1), (80, 8, 4), (30, 8, 4), (8, 4, 2),
])
@pytest.mark.parametrize("count", [0, 1, 3, 19, 20, 21, 100])
def test_all_values_are_transmitted(frameLen, dataLenFloat, dataLenInt, count):
    data = [float(i) for i in range(count)]
    frames = packArrayToFrame(10, data, frameLen, dataLenFloat, dataLenInt)
    assert all(f['id'] == 10 for f in frames)
    assert all(len(f['msg']) <= frameLen for f in frames)
    length, values = unpack(frames, dataLenFloat, dataLenInt)
    assert length == count
    assert values == data


def test_layout_is_unchanged():
    # 80 byte frames with 4 byte floats: 19 values in the first frame, 20 in the following ones
    frames = packArrayToFrame(1, list(range(40)), 80, 4, 4)
    assert [len(f['msg']) for f in frames] == [80, 80, 4]


def test_frame_too_small():
    with pytest.raises(ValueError):
        packArrayToFrame(1, [1.0], 2, 4, 4)
