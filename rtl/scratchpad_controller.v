// POLICY: 0 single; 1 fixed two-bank ping-pong; 2 availability-driven;
// 3 static cyclic multi-bank (literature-inspired buffering proxy);
// 4 runtime-adaptive effective depth over four physical banks.
module scratchpad_controller #(
    parameter DATA_WIDTH=8, ADDR_WIDTH=3, TILE_SIZE=4,
    parameter BANK_COUNT=4, NUMBER_OF_TILES=16,
    parameter MEMORY_TRANSFER_CYCLES=8, COMPUTE_CYCLES=8,
    parameter VARIABLE_LATENCY=0, POLICY=2, LATENCY_PROFILE=0,
    parameter OBS_WINDOW=32, STALL_HIGH_THRESHOLD=8,
    parameter STALL_LOW_THRESHOLD=2,
    parameter LOOKAHEAD_LOAD=0, LOOKAHEAD_COMPUTE=0)
  (input clk, input rst, output reg tile_done,
   output reg [31:0] result_tile, output reg [31:0] result_value,
   output reg [31:0] total_cycles, output reg [31:0] load_active_cycles,
   output reg [31:0] compute_active_cycles,
   output reg [31:0] compute_idle_cycles,
   output wire [31:0] stall_cycles,
   output reg [31:0] tiles_completed,
   output wire [31:0] total_mac_operations,
   output wire [2*BANK_COUNT-1:0] bank_state_debug,
   output reg load_busy, output wire compute_busy,
   output reg [31:0] active_load_bank,
   output reg [31:0] active_compute_bank,
   output reg [31:0] active_bank_limit,
   output reg [31:0] stall_count,
   output reg [31:0] observation_counter,
   output reg [31:0] no_ready_stall_cycles,
   output reg [31:0] active_bank_sum,
   output reg [31:0] time_in_2_bank_mode,
   output reg [31:0] time_in_3_bank_mode,
   output reg [31:0] time_in_4_bank_mode,
   output reg [31:0] mode_transitions);
  localparam EMPTY=0, LOADING=1, READY=2, COMPUTING=3;
  reg [1:0] bank_state [0:BANK_COUNT-1];
  reg [31:0] bank_tile [0:BANK_COUNT-1];
  reg [31:0] next_load, next_compute;
  reg [31:0] rr_load, rr_compute;
  reg [15:0] load_elapsed, load_target;
  reg mac_start;
  reg [31:0] mac_start_tile;
  reg [15:0] mac_start_cycles;
  wire mac_busy, mac_done, mac_rd_en, mac_finishing;
  wire [ADDR_WIDTH-1:0] mac_rd_addr;
  wire [31:0] mac_done_tile, mac_result;
  wire [2*DATA_WIDTH-1:0] ram_data [0:BANK_COUNT-1];
  wire [2*DATA_WIDTH-1:0] selected_data = ram_data[active_compute_bank];
  integer i, k, candidate, choice, scan, ready_count, stall_now;
  reg [31:0] chosen_tile;
  integer handoff_choice, handoff_scan, handoff_k;
  wire load_finishing = load_busy && (load_elapsed + 1 >= load_target);
  wire release_compute_bank = LOOKAHEAD_COMPUTE ? mac_finishing : mac_done;
  wire mac_issue = LOOKAHEAD_COMPUTE ? (handoff_choice >= 0) : mac_start;
  wire [31:0] issue_tile = LOOKAHEAD_COMPUTE ?
       (handoff_choice >= 0 ? bank_tile[handoff_choice] : 32'd0) : mac_start_tile;
  wire [15:0] issue_cycles = LOOKAHEAD_COMPUTE ? comp_cycles(issue_tile) :
                            mac_start_cycles;
  assign compute_busy = mac_busy;
  assign stall_cycles = compute_idle_cycles;
  assign total_mac_operations = tiles_completed * TILE_SIZE;
  function [15:0] mem_cycles;
    input [31:0] t;
    reg [15:0] extra;
    begin
      extra=0;
      if (LATENCY_PROFILE==2 && t>=NUMBER_OF_TILES/3 &&
          t<2*NUMBER_OF_TILES/3) begin
        case (t % 10)
          0: extra=0; 1: extra=16; 2: extra=0; 3: extra=10;
          4: extra=22; 5: extra=1; 6: extra=4; 7: extra=19;
          8: extra=0; default: extra=12;
        endcase
      end else if (LATENCY_PROFILE!=2 && VARIABLE_LATENCY != 0) begin
        case (t % 10)
          0: extra=0; 1: extra=8; 2: extra=0; 3: extra=7;
          4: extra=18; 5: extra=0; 6: extra=4; 7: extra=13;
          8: extra=2; default: extra=10;
        endcase
      end
      mem_cycles=MEMORY_TRANSFER_CYCLES+extra;
      if (mem_cycles<TILE_SIZE) mem_cycles=TILE_SIZE;
    end
  endfunction
  function [15:0] comp_cycles;
    input [31:0] t;
    reg [15:0] extra;
    begin
      extra=0;
      if (LATENCY_PROFILE==2) begin
        if (t<NUMBER_OF_TILES/3 || t>=2*NUMBER_OF_TILES/3)
          extra=12;
      end else if (VARIABLE_LATENCY != 0) begin
        case (t % 5)
          0: extra=0; 1: extra=4; 2: extra=0;
          3: extra=8; default: extra=2;
        endcase
      end
      comp_cycles=COMPUTE_CYCLES+extra;
      if (comp_cycles<TILE_SIZE+2) comp_cycles=TILE_SIZE+2;
    end
  endfunction
  function [DATA_WIDTH-1:0] act_value;
    input [31:0] t;
    input [15:0] index;
    begin act_value=((t+index)%15)+1; end
  endfunction
  function [DATA_WIDTH-1:0] weight_value;
    input [31:0] t;
    input [15:0] index;
    begin weight_value=((3*t+2*index)%15)+1; end
  endfunction
  // The next job may be selected while the current MAC job completes.
  // A completing load is also eligible: its final RAM write occurs on the
  // issue edge, and the new MAC's first synchronous read is one edge later.
  always @* begin
    handoff_choice=-1;
    handoff_scan=0;
    handoff_k=0;
    if (LOOKAHEAD_COMPUTE && (!mac_busy || mac_finishing)) begin
      for (handoff_k=0;handoff_k<BANK_COUNT;handoff_k=handoff_k+1) begin
        if (POLICY==2 || POLICY==4)
          handoff_scan=(rr_compute+handoff_k)%BANK_COUNT;
        else handoff_scan=handoff_k;
        if (handoff_choice<0 &&
            (bank_state[handoff_scan]==READY ||
             (load_finishing && active_load_bank==handoff_scan)) &&
            ((POLICY==2 || POLICY==4) ||
             bank_tile[handoff_scan]==next_compute))
          handoff_choice=handoff_scan;
      end
    end
  end
  genvar b;
  generate for (b=0; b<BANK_COUNT; b=b+1) begin: banks
    wire write_this = load_busy && active_load_bank==b && load_elapsed<TILE_SIZE;
    wire read_this = mac_rd_en && active_compute_bank==b;
    assign bank_state_debug[2*b +: 2] = bank_state[b];
    sync_ram #(.DATA_WIDTH(2*DATA_WIDTH), .ADDR_WIDTH(ADDR_WIDTH)) ram
      (.clk(clk), .wr_en(write_this), .wr_addr(load_elapsed[ADDR_WIDTH-1:0]),
       .wr_data({act_value(bank_tile[b],load_elapsed),
                 weight_value(bank_tile[b],load_elapsed)}),
       .rd_en(read_this), .rd_addr(mac_rd_addr), .rd_data(ram_data[b]));
  end endgenerate
  mac_engine #(.DATA_WIDTH(DATA_WIDTH), .TILE_SIZE(TILE_SIZE),
               .ADDR_WIDTH(ADDR_WIDTH), .CHAIN_START(LOOKAHEAD_COMPUTE)) mac
    (.clk(clk), .rst(rst), .start(mac_issue), .run_cycles(issue_cycles),
     .tile_id(issue_tile), .rd_data(selected_data),
     .rd_en(mac_rd_en), .rd_addr(mac_rd_addr), .busy(mac_busy),
     .done(mac_done), .finishing(mac_finishing),
     .done_tile(mac_done_tile), .result(mac_result));
  always @(posedge clk) begin
    if (rst) begin
      next_load<=0; next_compute<=0; rr_load<=0; rr_compute<=0;
      load_busy<=0; load_elapsed<=0; load_target<=0;
      active_load_bank<=0; active_compute_bank<=0;
      mac_start<=0; mac_start_tile<=0; mac_start_cycles<=0;
      tile_done<=0; result_tile<=0; result_value<=0;
      total_cycles<=0; load_active_cycles<=0;
      compute_active_cycles<=0; compute_idle_cycles<=0;
      tiles_completed<=0;
      active_bank_limit<=(POLICY==4 ? 2 : BANK_COUNT);
      stall_count<=0; observation_counter<=0;
      no_ready_stall_cycles<=0; active_bank_sum<=0;
      time_in_2_bank_mode<=0; time_in_3_bank_mode<=0;
      time_in_4_bank_mode<=0; mode_transitions<=0;
      for (i=0;i<BANK_COUNT;i=i+1) begin
        bank_state[i]<=EMPTY; bank_tile[i]<=0;
      end
    end else begin
      mac_start<=0; tile_done<=0;
      if (tiles_completed<NUMBER_OF_TILES) begin
        total_cycles<=total_cycles+1;
        if (load_busy) load_active_cycles<=load_active_cycles+1;
        if (mac_busy) compute_active_cycles<=compute_active_cycles+1;
        else compute_idle_cycles<=compute_idle_cycles+1;
        if (POLICY==4) begin
          active_bank_sum<=active_bank_sum+active_bank_limit;
          case (active_bank_limit)
            2: time_in_2_bank_mode<=time_in_2_bank_mode+1;
            3: time_in_3_bank_mode<=time_in_3_bank_mode+1;
            4: time_in_4_bank_mode<=time_in_4_bank_mode+1;
          endcase
          ready_count=0;
          for (k=0;k<BANK_COUNT;k=k+1)
            if (bank_state[k]==READY) ready_count=ready_count+1;
          stall_now=(!mac_busy && !mac_issue && !mac_done &&
                     ready_count==0) ? 1 : 0;
          if (stall_now!=0) no_ready_stall_cycles<=no_ready_stall_cycles+1;
          if (observation_counter+1>=OBS_WINDOW) begin
            observation_counter<=0; stall_count<=0;
            if (stall_count+stall_now>=STALL_HIGH_THRESHOLD &&
                active_bank_limit<4) begin
              active_bank_limit<=active_bank_limit+1;
              mode_transitions<=mode_transitions+1;
            end else if (stall_count+stall_now<=STALL_LOW_THRESHOLD &&
                         active_bank_limit>2) begin
              active_bank_limit<=active_bank_limit-1;
              mode_transitions<=mode_transitions+1;
            end
          end else begin
            observation_counter<=observation_counter+1;
            stall_count<=stall_count+stall_now;
          end
        end
      end
      if (load_busy) begin
        load_elapsed<=load_elapsed+1;
        if (load_elapsed+1>=load_target) begin
          load_busy<=0;
          bank_state[active_load_bank]<=READY;
        end
      end
      if (release_compute_bank) bank_state[active_compute_bank]<=EMPTY;
      if (mac_done) begin
        tile_done<=1; result_tile<=mac_done_tile; result_value<=mac_result;
        tiles_completed<=tiles_completed+1;
      end
      // Legacy mode retains registered handoff timing. Look-ahead may
      // accept the next load on completion and reclaim a just-released bank.
      if ((!load_busy || (LOOKAHEAD_LOAD && load_finishing)) &&
          next_load<NUMBER_OF_TILES) begin
        choice=-1;
        if (POLICY==2 || POLICY==4) begin
          for (k=0;k<BANK_COUNT;k=k+1) begin
            scan=(rr_load+k)%BANK_COUNT;
            if (choice<0 && (bank_state[scan]==EMPTY ||
                (LOOKAHEAD_LOAD && release_compute_bank &&
                 active_compute_bank==scan)) &&
                (POLICY!=4 || scan<active_bank_limit)) choice=scan;
          end
        end else begin
          candidate=next_load%BANK_COUNT;
          if (bank_state[candidate]==EMPTY ||
              (LOOKAHEAD_LOAD && release_compute_bank &&
               active_compute_bank==candidate)) choice=candidate;
        end
        if (choice>=0) begin
          bank_state[choice]<=LOADING;
          bank_tile[choice]<=next_load;
          active_load_bank<=choice;
          load_busy<=1; load_elapsed<=0;
          load_target<=mem_cycles(next_load);
          next_load<=next_load+1;
          rr_load<=(choice+1)%BANK_COUNT;
        end
      end
      if (LOOKAHEAD_COMPUTE) begin
        if (handoff_choice>=0) begin
          bank_state[handoff_choice]<=COMPUTING;
          active_compute_bank<=handoff_choice;
          next_compute<=next_compute+1;
          rr_compute<=(handoff_choice+1)%BANK_COUNT;
        end
      end else if (!mac_busy && !mac_start && !mac_done) begin
        choice=-1;
        if (POLICY==2 || POLICY==4) begin
          for (k=0;k<BANK_COUNT;k=k+1) begin
            scan=(rr_compute+k)%BANK_COUNT;
            if (choice<0 && bank_state[scan]==READY) choice=scan;
          end
        end else begin
          for (k=0;k<BANK_COUNT;k=k+1)
            if (choice<0 && bank_state[k]==READY &&
                bank_tile[k]==next_compute) choice=k;
        end
        if (choice>=0) begin
          chosen_tile=bank_tile[choice];
          bank_state[choice]<=COMPUTING;
          active_compute_bank<=choice;
          mac_start<=1; mac_start_tile<=chosen_tile;
          mac_start_cycles<=comp_cycles(chosen_tile);
          next_compute<=next_compute+1;
          rr_compute<=(choice+1)%BANK_COUNT;
        end
      end
    end
  end
endmodule
