import pathlib

import numpy as np

from apple_hdr_heic import (
    combine_hdrgainmap,
    displayp3_to_bt2020,
    load_and_combine_gainmap,
    load_as_bt2100_pq,
    quantize_to_uint16,
)

DATA_DIR = pathlib.Path(__file__).parent.absolute() / "data"


def test_quantize():
    arr1 = np.array([0.0, 0.1, 0.9, 1.0])
    qarr1 = quantize_to_uint16(arr1)
    assert np.all(qarr1 == np.array([0, 6554, 58982, 0xFFFF]))
    assert qarr1.dtype == np.uint16

    arr2 = np.array([-0.5, 2.0])
    qarr2 = quantize_to_uint16(arr2)
    assert np.all(qarr2 == np.array([0, 0xFFFF]))


def test_combine():
    test_sdr = np.linspace(0., 1.0, num=12, dtype=np.float32).reshape(2, 2, 3)
    test_gainmap = np.linspace(0., 1.0, num=4, dtype=np.float32).reshape(2, 2)
    headroom = 4.0
    combined = combine_hdrgainmap(test_sdr, test_gainmap, headroom)
    assert np.all(0 <= combined)
    assert np.all(combined <= headroom)
    assert combined.dtype == np.float32
    quant_combined = quantize_to_uint16(combined / headroom)
    qc_expected = [[[0, 142, 454], [1260, 2268, 3635]],
                   [[9344, 13107, 17630], [41622, 52790, 0xFFFF]]]
    assert np.all(quant_combined == qc_expected)


def test_dp3_to_bt2020():
    dp3 = np.array([[[0, 0, 0], [1, 1, 1]],
                    [[2, 0, 0], [0, 2, 2]]], dtype=np.float32)
    bt2020 = displayp3_to_bt2020(dp3)
    assert np.all(bt2020 >= 0)
    assert bt2020.dtype == np.float32
    bt2020_expected = [[[0., 0., 0.], [1., 1., 1.]],
                       [[1.5076661, 0.0914877, 0.0], [0.49233395, 1.9085124, 2.0024207]]]
    assert np.allclose(bt2020, bt2020_expected)


def test_load_and_combine():
    dp3_hdr = load_and_combine_gainmap(DATA_DIR / "hdr-sample.heic")
    assert np.all(dp3_hdr >= 0.0)
    assert np.all(dp3_hdr <= 7.38)  # note: 7.3717 is the headroom
    assert dp3_hdr.dtype == np.float32


def test_load_as_bt2100_pq():
    bt2100_pq = load_as_bt2100_pq(DATA_DIR / "hdr-sample.heic")
    assert np.all(bt2100_pq >= 0.0)
    assert np.all(bt2100_pq <= 0.8)
    assert bt2100_pq.dtype == np.float32
