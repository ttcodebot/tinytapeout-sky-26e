# SPDX-License-Identifier: Apache-2.0

# Chip level test of the micro tile container: selects the container through the mux, then
# selects each of its four micro tiles with uio_in[1:0] and compares uo_out, cycle by cycle,
# with an RTL reference model of the container that is driven by the same pins
# (micro_tiles_ref.v, instantiated in the testbench).

import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge

from test_mux import enable_design

CONTAINER = "tt_um_micro_tiles_group_1"
MICRO_TILES = 4
CYCLES = 400


def container_address():
    index_path = os.path.join(os.path.dirname(__file__), "../../../shuttle_index.json")
    with open(index_path) as f:
        index = json.load(f)
    return next(p["address"] for p in index["projects"] if p["macro"] == CONTAINER)


@cocotb.test()
async def test_micro_tiles(dut):
    # Slow clock: the gate level netlists have unit delays, and outputs are compared half a
    # cycle after the clock edge
    clock = Clock(dut.clk, 1000, unit="ns")
    cocotb.start_soon(clock.start())

    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.reset_n.value = 0
    address = container_address()
    await enable_design(dut, address)

    rng = random.Random(1)
    for sel in range(MICRO_TILES):
        dut._log.info(f"micro tile {sel} of {CONTAINER} (mux address {address})")
        await FallingEdge(dut.clk)
        dut.uio_in.value = sel
        dut.ui_in.value = 0
        dut.reset_n.value = 0
        await ClockCycles(dut.clk, 5)
        await FallingEdge(dut.clk)
        dut.reset_n.value = 1

        compared = 0
        values = set()
        for cycle in range(CYCLES):
            await FallingEdge(dut.clk)
            expected = dut.ref_uo_out.value
            if expected.is_resolvable:
                actual = dut.uo_out.value
                assert actual.is_resolvable and int(actual) == int(expected), (
                    f"micro tile {sel}, cycle {cycle}: uo_out is {actual}, expected {expected}"
                )
                compared += 1
                values.add(int(expected))
            # New inputs every few cycles, and a reset in the middle of the run
            if cycle % 3 == 0:
                dut.ui_in.value = rng.randrange(256)
            dut.reset_n.value = 0 if CYCLES // 2 <= cycle < CYCLES // 2 + 3 else 1

        dut._log.info(f"micro tile {sel}: {compared} of {CYCLES} cycles compared, {len(values)} different output values")
        assert compared >= CYCLES // 2, f"micro tile {sel}: reference output is unknown most of the time"
        assert len(values) >= 4, f"micro tile {sel}: output hardly changes, the test is not meaningful"
