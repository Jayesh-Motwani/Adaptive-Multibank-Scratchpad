// One MAC per issued RAM word. The RAM read is synchronous, so a valid pipeline
// bit delays accumulation by one clock. run_cycles must be >= TILE_SIZE+2.
module mac_engine #(parameter DATA_WIDTH=8, parameter TILE_SIZE=4,
                    parameter ADDR_WIDTH=3, parameter CHAIN_START=0)
  (input clk, input rst, input start, input [15:0] run_cycles,
   input [31:0] tile_id, input [2*DATA_WIDTH-1:0] rd_data,
   output wire rd_en, output wire [ADDR_WIDTH-1:0] rd_addr,
   output reg busy, output reg done, output wire finishing,
   output reg [31:0] done_tile,
   output reg [31:0] result);
  reg [15:0] elapsed;
  reg [15:0] target;
  reg [15:0] issued;
  reg [15:0] consumed;
  reg valid_d;
  reg [31:0] accumulator;
  reg [31:0] active_tile;
  wire [DATA_WIDTH-1:0] activation = rd_data[2*DATA_WIDTH-1:DATA_WIDTH];
  wire [DATA_WIDTH-1:0] weight = rd_data[DATA_WIDTH-1:0];
  assign rd_en = busy && (issued < TILE_SIZE);
  assign rd_addr = issued[ADDR_WIDTH-1:0];
  // All synchronous RAM responses have been accumulated before this edge.
  // It is then safe to publish the old result and accept a new descriptor.
  assign finishing = busy && (elapsed + 1 >= target) &&
                     (consumed == TILE_SIZE);
  always @(posedge clk) begin
    if (rst) begin
      busy <= 0; done <= 0; done_tile <= 0; result <= 0;
      elapsed <= 0; target <= 0; issued <= 0; consumed <= 0;
      valid_d <= 0; accumulator <= 0; active_tile <= 0;
    end else begin
      done <= 0;
      if (busy) begin
        elapsed <= elapsed + 1;
        valid_d <= rd_en;
        if (rd_en) issued <= issued + 1;
        if (valid_d) begin
          accumulator <= accumulator + activation * weight;
          consumed <= consumed + 1;
        end
        if (finishing) begin
          busy <= 0; done <= 1; done_tile <= active_tile;
          result <= accumulator;
        end
      end
      if (start && (!busy || (CHAIN_START && finishing))) begin
        busy <= 1; elapsed <= 0; target <= run_cycles;
        issued <= 0; consumed <= 0; valid_d <= 0;
        accumulator <= 0; active_tile <= tile_id;
      end
    end
  end
endmodule
