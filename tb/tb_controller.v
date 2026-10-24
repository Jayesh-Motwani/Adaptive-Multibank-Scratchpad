`timescale 1ns/1ps
module tb_controller;
  parameter POLICY=2, BANK_COUNT=4, NUMBER_OF_TILES=16;
  parameter TILE_SIZE=4, DATA_WIDTH=8, ADDR_WIDTH=3;
  parameter MEMORY_TRANSFER_CYCLES=8, COMPUTE_CYCLES=8;
  parameter VARIABLE_LATENCY=0, LATENCY_PROFILE=0;
  parameter OBS_WINDOW=32, STALL_HIGH_THRESHOLD=8, STALL_LOW_THRESHOLD=2;
  parameter LOOKAHEAD_LOAD=0, LOOKAHEAD_COMPUTE=0;
  parameter TRACE_HANDOFF=0;
  reg clk=0, rst=1;
  always #5 clk=~clk;
  wire tile_done, compute_busy, load_busy;
  wire [31:0] result_tile, result_value, total_cycles;
  wire [31:0] load_active_cycles, compute_active_cycles;
  wire [31:0] compute_idle_cycles, stall_cycles, tiles_completed;
  wire [31:0] total_mac_operations, active_load_bank, active_compute_bank;
  wire [2*BANK_COUNT-1:0] bank_state_debug;
  wire [31:0] active_bank_limit, stall_count, observation_counter;
  wire [31:0] no_ready_stall_cycles, active_bank_sum;
  wire [31:0] time_in_2_bank_mode, time_in_3_bank_mode;
  wire [31:0] time_in_4_bank_mode, mode_transitions;
  reg [2*BANK_COUNT-1:0] previous_states;
  reg [31:0] previous_limit;
  reg previous_valid;
  reg [NUMBER_OF_TILES-1:0] seen;
  reg [NUMBER_OF_TILES-1:0] started;
  integer starts;
  integer checks, i, loading_count, computing_count, timeout;
  integer expected, a, w;
  reg [1023:0] vcd_name;
  scratchpad_controller #(
    .DATA_WIDTH(DATA_WIDTH), .ADDR_WIDTH(ADDR_WIDTH),
    .TILE_SIZE(TILE_SIZE), .BANK_COUNT(BANK_COUNT),
    .NUMBER_OF_TILES(NUMBER_OF_TILES),
    .MEMORY_TRANSFER_CYCLES(MEMORY_TRANSFER_CYCLES),
    .COMPUTE_CYCLES(COMPUTE_CYCLES),
    .VARIABLE_LATENCY(VARIABLE_LATENCY), .POLICY(POLICY),
    .LATENCY_PROFILE(LATENCY_PROFILE), .OBS_WINDOW(OBS_WINDOW),
    .STALL_HIGH_THRESHOLD(STALL_HIGH_THRESHOLD),
    .STALL_LOW_THRESHOLD(STALL_LOW_THRESHOLD),
    .LOOKAHEAD_LOAD(LOOKAHEAD_LOAD),
    .LOOKAHEAD_COMPUTE(LOOKAHEAD_COMPUTE)) dut
    (.clk(clk), .rst(rst), .tile_done(tile_done),
     .result_tile(result_tile), .result_value(result_value),
     .total_cycles(total_cycles), .load_active_cycles(load_active_cycles),
     .compute_active_cycles(compute_active_cycles),
     .compute_idle_cycles(compute_idle_cycles), .stall_cycles(stall_cycles),
     .tiles_completed(tiles_completed),
     .total_mac_operations(total_mac_operations),
     .bank_state_debug(bank_state_debug), .load_busy(load_busy),
     .compute_busy(compute_busy), .active_load_bank(active_load_bank),
     .active_compute_bank(active_compute_bank),
     .active_bank_limit(active_bank_limit), .stall_count(stall_count),
     .observation_counter(observation_counter),
     .no_ready_stall_cycles(no_ready_stall_cycles),
     .active_bank_sum(active_bank_sum),
     .time_in_2_bank_mode(time_in_2_bank_mode),
     .time_in_3_bank_mode(time_in_3_bank_mode),
     .time_in_4_bank_mode(time_in_4_bank_mode),
     .mode_transitions(mode_transitions));
  task fail;
    input [255:0] reason;
    begin $display("STATUS=FAIL REASON=%s",reason); $finish; end
  endtask
  initial begin
    seen=0; started=0; starts=0; checks=0; timeout=0;
    previous_states=0; previous_limit=0; previous_valid=0;
    if ($value$plusargs("VCD=%s",vcd_name)) begin
      $dumpfile(vcd_name); $dumpvars(0,tb_controller);
    end
    repeat (3) @(negedge clk);
    rst=0;
  end
  // Check the descriptor on the edge the MAC actually accepts it. This
  // covers an old result completing while the next job starts on that edge.
  always @(posedge clk) if (!rst) begin
    if (TRACE_HANDOFF && dut.load_finishing)
      $display("LOAD_FINISH CYCLE=%0d TILE=%0d BANK=%0d",
               total_cycles+1,dut.bank_tile[active_load_bank],active_load_bank);
    if (TRACE_HANDOFF && dut.mac_finishing)
      $display("MAC_FINISH CYCLE=%0d TILE=%0d BANK=%0d",
               total_cycles+1,dut.mac.active_tile,active_compute_bank);
    if (dut.mac_issue) begin
      if (compute_busy && !(LOOKAHEAD_COMPUTE && dut.mac_finishing))
        fail("MAC issued while unavailable");
      if (dut.issue_tile>=NUMBER_OF_TILES) fail("issue tile ID out of range");
      if (started[dut.issue_tile]) fail("duplicate MAC issue");
      started[dut.issue_tile]=1;
      starts=starts+1;
      if (TRACE_HANDOFF)
        $display("MAC_ACCEPT CYCLE=%0d TILE=%0d BANK=%0d",
                 total_cycles+1,dut.issue_tile,
                 LOOKAHEAD_COMPUTE ? dut.handoff_choice : active_compute_bank);
    end
    if (compute_busy && bank_state_debug[2*active_compute_bank +: 2]!=3)
      fail("MAC bank state mismatch");
    if (load_busy && dut.mac_rd_en && active_load_bank==active_compute_bank)
      fail("read/write bank collision");
  end
  always @(negedge clk) if (!rst) begin
    if (TRACE_HANDOFF && load_busy && dut.load_elapsed==0)
      $display("LOAD_ACCEPT CYCLE=%0d TILE=%0d BANK=%0d",
               total_cycles,dut.bank_tile[active_load_bank],active_load_bank);
    timeout=timeout+1;
    if (timeout>NUMBER_OF_TILES*(MEMORY_TRANSFER_CYCLES+
        COMPUTE_CYCLES+64)+100) fail("timeout");
    loading_count=0; computing_count=0;
    for (i=0;i<BANK_COUNT;i=i+1) begin
      if (bank_state_debug[2*i +: 2]==1) loading_count=loading_count+1;
      if (bank_state_debug[2*i +: 2]==3) computing_count=computing_count+1;
      if (POLICY==4 && previous_valid &&
          previous_states[2*i +: 2]!=1 &&
          bank_state_debug[2*i +: 2]==1 && i>=previous_limit)
        fail("allocated inactive bank");
    end
    previous_states=bank_state_debug;
    previous_limit=active_bank_limit;
    previous_valid=1;
    if (loading_count>1 || computing_count>1) fail("resource overlap");
    if (load_busy && bank_state_debug[2*active_load_bank +: 2]!=1)
      fail("loader state mismatch");
    if (POLICY==4 && (active_bank_limit<2 || active_bank_limit>4))
      fail("active bank limit out of range");
    if (tile_done) begin
      if (result_tile>=NUMBER_OF_TILES) fail("tile ID out of range");
      if (seen[result_tile]) fail("duplicate tile");
      expected=0;
      for (i=0;i<TILE_SIZE;i=i+1) begin
        a=((result_tile+i)%15)+1;
        w=((3*result_tile+2*i)%15)+1;
        expected=expected+a*w;
      end
      if (result_value!==expected) begin
        $display("TILE=%0d EXPECTED=%0d ACTUAL=%0d",
                 result_tile,expected,result_value);
        fail("MAC mismatch");
      end
      seen[result_tile]=1; checks=checks+1;
      $display("TILE_PASS=%0d RESULT=%0d",result_tile,result_value);
      if (checks==NUMBER_OF_TILES) begin
        if (starts!=NUMBER_OF_TILES || started!={NUMBER_OF_TILES{1'b1}})
          fail("MAC issue accounting");
        if (tiles_completed!=NUMBER_OF_TILES) fail("completion counter");
        if (total_cycles!=compute_active_cycles+compute_idle_cycles)
          fail("cycle accounting");
        if (stall_cycles!=compute_idle_cycles) fail("stall accounting");
        if (total_mac_operations!=NUMBER_OF_TILES*TILE_SIZE)
          fail("MAC count");
        if (POLICY==4 && time_in_2_bank_mode+time_in_3_bank_mode+
            time_in_4_bank_mode!=total_cycles) fail("mode time accounting");
        $display("POLICY=%0d",POLICY);
        $display("BANKS=%0d",BANK_COUNT);
        $display("TILES=%0d",NUMBER_OF_TILES);
        $display("TILE_SIZE=%0d",TILE_SIZE);
        $display("MEM_CYCLES=%0d",MEMORY_TRANSFER_CYCLES);
        $display("COMPUTE_CYCLES=%0d",COMPUTE_CYCLES);
        $display("VARIABLE_LATENCY=%0d",VARIABLE_LATENCY);
        $display("LATENCY_PROFILE=%0d",LATENCY_PROFILE);
        $display("LOOKAHEAD_LOAD=%0d",LOOKAHEAD_LOAD);
        $display("LOOKAHEAD_COMPUTE=%0d",LOOKAHEAD_COMPUTE);
        $display("TOTAL_CYCLES=%0d",total_cycles);
        $display("LOAD_ACTIVE_CYCLES=%0d",load_active_cycles);
        $display("COMPUTE_ACTIVE_CYCLES=%0d",compute_active_cycles);
        $display("COMPUTE_IDLE_CYCLES=%0d",compute_idle_cycles);
        $display("STALL_CYCLES=%0d",stall_cycles);
        $display("TILES_COMPLETED=%0d",tiles_completed);
        $display("TOTAL_MAC_OPERATIONS=%0d",total_mac_operations);
        $display("ACTIVE_BANK_LIMIT=%0d",active_bank_limit);
        $display("ACTIVE_BANK_SUM=%0d",active_bank_sum);
        $display("TIME_IN_2_BANK_MODE=%0d",time_in_2_bank_mode);
        $display("TIME_IN_3_BANK_MODE=%0d",time_in_3_bank_mode);
        $display("TIME_IN_4_BANK_MODE=%0d",time_in_4_bank_mode);
        $display("MODE_TRANSITIONS=%0d",mode_transitions);
        $display("NO_READY_STALL_CYCLES=%0d",no_ready_stall_cycles);
        $display("CHECKS=%0d",checks);
        $display("STATUS=PASS");
        $finish;
      end
    end
  end
endmodule
