from routing.checks import Checker, Port, compiles, counterexample, mismatches, ports

SPEC = """
 - input  a
 - input  b   ( 4 bits)
 - input  i,
 - output out (4 bits)
"""

AND = """module TopModule(input a, input [3:0] b, input i, output [3:0] out);
  assign out = b & {4{a}};
endmodule
"""
# Same function, written differently, with a helper module.
AND_VIA_HELPER = """module gate(input x, input [3:0] y, output [3:0] z);
  assign z = x ? y : 4'b0;
endmodule
module TopModule(input a, input [3:0] b, input i, output [3:0] out);
  gate g(.x(a), .y(b), .z(out));
endmodule
"""
OR = """module TopModule(input a, input [3:0] b, input i, output [3:0] out);
  assign out = b | {4{a}};
endmodule
"""
DONT_CARE = """module TopModule(input a, input [3:0] b, input i, output [3:0] out);
  assign out = a ? b : 4'bx;
endmodule
"""

COUNTER_SPEC = """
 - input  clk
 - input  reset
 - output q (4 bits)
"""
COUNTER = """module TopModule(input clk, input reset, output reg [3:0] q);
  always @(posedge clk) q <= reset ? 4'd0 : q + 1;
endmodule
"""
COUNTER_BY_TWO = """module TopModule(input clk, input reset, output reg [3:0] q);
  always @(posedge clk) q <= reset ? 4'd0 : q + 2;
endmodule
"""


def test_parses_ports_with_loose_spacing():
    assert ports(SPEC) == [
        Port("input", "a", 1),
        Port("input", "b", 4),
        Port("input", "i", 1),
        Port("output", "out", 4),
    ]


def test_compile_check():
    assert compiles(AND)
    assert not compiles("module TopModule(output x);\n  assign x = ;\nendmodule\n")
    assert not compiles("module top_module(output x);\nendmodule\n")


def test_equivalent_designs_agree_even_with_shared_names():
    assert mismatches(SPEC, AND, AND_VIA_HELPER) == 0
    assert mismatches(SPEC, AND_VIA_HELPER, AND_VIA_HELPER) == 0


def test_different_designs_disagree():
    assert mismatches(SPEC, AND, OR) > 0


def test_x_outputs_match_anything():
    assert mismatches(SPEC, AND, DONT_CARE) == 0


def test_clocked_designs_are_compared_cycle_by_cycle():
    assert mismatches(COUNTER_SPEC, COUNTER, COUNTER) == 0
    assert mismatches(COUNTER_SPEC, COUNTER, COUNTER_BY_TWO) > 0


def test_broken_design_never_agrees():
    checker = Checker({"t": SPEC})
    assert not checker.agree("t", AND, "module TopModule(\n")
    assert not checker.agree("t", "module TopModule(\n", "module TopModule(\n")
    assert checker.agree("t", AND, AND_VIA_HELPER)


def test_counterexample_ends_at_the_first_mismatch():
    trace = counterexample(COUNTER_SPEC, COUNTER, COUNTER_BY_TWO)
    rows = trace.splitlines()
    assert rows[1] == "sample | when | reset | q (A) | q (B)"
    assert rows[-1].endswith("| 1 | 2")


def test_no_counterexample_for_equivalent_designs():
    assert counterexample(SPEC, AND, AND_VIA_HELPER) is None
