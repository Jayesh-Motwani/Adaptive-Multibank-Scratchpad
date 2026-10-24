// Behavioral synchronous scratchpad RAM. No physical SRAM claims are implied.
module sync_ram #(parameter DATA_WIDTH=16, parameter ADDR_WIDTH=3)
  (input clk, input wr_en, input [ADDR_WIDTH-1:0] wr_addr,
   input [DATA_WIDTH-1:0] wr_data, input rd_en,
   input [ADDR_WIDTH-1:0] rd_addr, output reg [DATA_WIDTH-1:0] rd_data);
  reg [DATA_WIDTH-1:0] mem [0:(1<<ADDR_WIDTH)-1];
  always @(posedge clk) begin
    if (wr_en) mem[wr_addr] <= wr_data;
    if (rd_en) rd_data <= mem[rd_addr];
  end
endmodule
