import pathlib

import numpy as np

from apple_hdr_heic import (
    apply_hdrgainmap,
    clipped_colorspace_transform,
    load_as_bt2020_linear,
    load_as_displayp3_linear,
    quantize_bt2020_to_bt2100_pq,
)
from apple_hdr_heic.lib import quantize_unit_interval_to_uint16

DATA_DIR = pathlib.Path(__file__).parent.absolute() / "data"


def test_quantize_unit_interval() -> None:
    arr1 = np.array([0.0, 0.1, 0.9, 1.0], dtype=np.float32)
    qarr1 = quantize_unit_interval_to_uint16(arr1)
    assert np.all(qarr1 == np.array([0, 6554, 58982, 0xFFFF]))
    assert qarr1.dtype == np.uint16

    arr2 = np.array([-0.5, 2.0], dtype=np.float32)
    qarr2 = quantize_unit_interval_to_uint16(arr2)
    assert np.all(qarr2 == np.array([0, 0xFFFF]))


def test_apply_hdrgainmap() -> None:
    test_sdr = np.linspace(0.0, 1.0, num=12, dtype=np.float32).reshape(2, 2, 3)
    test_gainmap = np.linspace(0.0, 1.0, num=4, dtype=np.float32).reshape(2, 2)
    headroom = 4.0
    test_hdr = apply_hdrgainmap(test_sdr, test_gainmap, headroom)
    assert np.all(0 <= test_hdr)
    assert np.all(test_hdr <= headroom)
    assert test_hdr.dtype == np.float32
    quant_hdr = quantize_unit_interval_to_uint16(test_hdr / headroom)
    qc_expected = [[[0, 142, 454], [1260, 2268, 3635]],
                   [[9344, 13107, 17630], [41622, 52790, 0xFFFF]]]  # fmt: skip
    assert np.all(quant_hdr == qc_expected)


def test_clipped_colorspace_transform() -> None:
    dp3 = np.array([[[0, 0, 0], [1, 1, 1]],
                    [[2, 0, 0], [0, 2, 2]]], dtype=np.float32)  # fmt: skip
    bt2020 = clipped_colorspace_transform(dp3, "Display P3", "ITU-R BT.2020")
    assert np.all(bt2020 >= 0)
    assert bt2020.dtype == np.float32
    bt2020_expected = [[[0., 0., 0.], [1., 1., 1.]],
                       [[1.5076661, 0.0914877, 0.0], [0.49233395, 1.9085124, 2.0024207]]]  # fmt: skip
    assert np.allclose(bt2020, bt2020_expected)


def test_load_as_dp3_lin() -> None:
    dp3_lin = load_as_displayp3_linear(DATA_DIR / "hdr-sample.heic")
    assert np.all(dp3_lin >= 0.0)
    assert np.all(dp3_lin <= 7.372)  # note: 7.3717 is the headroom
    assert dp3_lin.dtype == np.float32


def test_load_as_bt2100_lin() -> None:
    bt2020_lin = load_as_bt2020_linear(DATA_DIR / "hdr-sample.heic")
    assert np.all(bt2020_lin >= 0.0)
    assert np.all(bt2020_lin <= 7.3721)
    assert bt2020_lin.dtype == np.float32


def test_quantize_bt2100_pq() -> None:
    bt2020 = np.array([[[0, 0, 0], [1, 1, 1]],
                       [[2, 0, 0], [0, 2, 2]]], dtype=np.float32)  # fmt: skip
    bt2100_pq = quantize_bt2020_to_bt2100_pq(bt2020)
    assert bt2100_pq.dtype == np.uint16
    bt2100_pq_expected = [[[0, 0, 0], [38056, 38056, 38056]],
                          [[42871, 0, 0], [0, 42871, 42871]]]  # fmt: skip
    assert np.all(bt2100_pq == bt2100_pq_expected)
