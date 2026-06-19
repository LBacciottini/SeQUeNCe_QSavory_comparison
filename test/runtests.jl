using SeQUeNCeQSavoryComparison
using Test
using ConcurrentSim

const QS = SeQUeNCeQSavoryComparison

@testset "config and formulas" begin
    cfg = load_config(joinpath(@__DIR__, "..", "configs", "default.toml"))
    resolved = resolve_config(cfg)
    derived = resolved["derived"]

    @test derived["half_link_km"] ≈ 5.0
    @test 0 < derived["arm_transmissivity"] < 1
    @test derived["source_transmissivity"] ≈
        cfg["memories"]["emission_efficiency"] *
        cfg["optics"]["collection_efficiency"] *
        cfg["optics"]["frequency_conversion_efficiency"]
    @test derived["arm_transmissivity"] ≈ derived["source_transmissivity"] * derived["fiber_transmissivity_half_link"]
    @test 0 < derived["barrett_kok_success_probability"] < 1
    @test 0 < derived["barrett_kok_raw_fidelity"] <= 1
    @test derived["barrett_kok_full_success_probability"] ≈ derived["barrett_kok_success_probability"]
    @test derived["barrett_kok_round2_entry_probability"] ≈ sqrt(derived["barrett_kok_full_success_probability"])
    @test derived["barrett_kok_effective_attempt_time_s"] ≈
        derived["barrett_kok_round1_time_s"] +
        derived["barrett_kok_round2_entry_probability"] * derived["barrett_kok_round2_time_s"]
    @test derived["barrett_kok_resource_request_arrival_ps"] == 50_000_000
    @test derived["barrett_kok_protocol_start_nonprimary_ps"] == 100_000_000
    @test derived["barrett_kok_round1_min_emit_ps"] == 150_000_000
    @test derived["barrett_kok_round1_emit_ps"] == 150_000_000
    @test derived["barrett_kok_round1_failure_time_ps"] == 225_000_010
    @test derived["barrett_kok_round2_min_emit_ps"] == 325_000_010
    @test derived["barrett_kok_round2_emit_ps"] == 325_012_500
    @test derived["barrett_kok_two_round_time_ps"] == 400_012_510
    @test derived["barrett_kok_round2_increment_time_ps"] == 175_012_500
    @test derived["barrett_kok_round1_time_s"] ≈ 0.00022500001
    @test derived["barrett_kok_round2_time_s"] ≈ 0.0001750125
    @test derived["barrett_kok_two_round_time_s"] ≈ 0.00040001251
    @test derived["barrett_kok_round1_time_s"] < derived["barrett_kok_effective_attempt_time_s"] < 2 * derived["barrett_kok_round1_time_s"]
    @test derived["barrett_kok_expected_rate_hz"] ≈
        derived["barrett_kok_full_success_probability"] / derived["barrett_kok_effective_attempt_time_s"]

    applied = inspect_qsavory_configuration(cfg)
    applied_werner = inspect_qsavory_configuration(cfg; raw_state_model="werner")
    bad_swap_cfg = deepcopy(cfg)
    bad_swap_cfg["swapping"]["degradation"] = 0.95
    @test_throws ArgumentError resolve_config(bad_swap_cfg)
    bad_lane_cfg = deepcopy(cfg)
    bad_lane_cfg["resource_reservation"]["flow2"]["r3_slots"] = [0, 8]
    @test_throws ArgumentError resolve_config(bad_lane_cfg)
    @test applied["register_counts"]["r1"] == cfg["memories"]["r1_count"]
    @test applied["memory_noise"]["background"] == "none"
    @test applied["raw_state"]["model"] == "exact"
    @test applied["raw_state"]["simulator_label"] == "qsavory_exact"
    @test applied["raw_state"]["class"] == "BarrettKokBellPair"
    @test applied["raw_state"]["fidelity_observables"]["flow1"] == "psi_plus_01"
    @test applied["raw_state"]["fidelity_observables"]["flow2"] == "phi_plus_00_11"
    @test applied["raw_state"]["raw_fidelity"] == derived["barrett_kok_raw_fidelity"]
    @test applied_werner["raw_state"]["model"] == "werner"
    @test applied_werner["raw_state"]["simulator_label"] == "qsavory_werner"
    @test applied_werner["raw_state"]["class"] == "DepolarizedBellPair"
    @test applied_werner["raw_state"]["fidelity_observables"]["flow1"] == "phi_plus_00_11"
    @test applied_werner["raw_state"]["fidelity_observables"]["flow2"] == "phi_plus_00_11"
    @test applied_werner["raw_state"]["raw_fidelity"] == derived["barrett_kok_raw_fidelity"]
    @test applied_werner["raw_state"]["werner_depolarization_parameter"] ≈
        (4 * derived["barrett_kok_raw_fidelity"] - 1) / 3
    @test_throws ArgumentError inspect_qsavory_configuration(cfg; raw_state_model="bad")
    @test applied["slot_ranges"]["flow2_r2_left_slots"] == cfg["resource_reservation"]["flow2"]["r2_left_slots"]
    @test applied["distillation"]["scope"] == "end_to_end_only"
    @test applied["distillation"]["nodeA"] == "r1"
    @test applied["distillation"]["nodeB"] == "r3"
    @test applied["swapping"]["fidelity_model"] == "ideal"
    @test applied["swapping"]["retry_policy"] == "event_based"
    @test isnothing(applied["swapping"]["retry_lock_time"])
    @test applied["entangler"]["success_probability"] == derived["barrett_kok_full_success_probability"]
    @test applied["entangler"]["effective_attempt_time_s"] == derived["barrett_kok_effective_attempt_time_s"]
    @test applied["entangler"]["multiplexing"] == "one_entangler_per_reserved_memory_lane"
    @test applied["entangler"]["lane_counts"]["flow1_r1_r2"] == 10
    @test applied["entangler"]["lane_counts"]["flow2_r1_r2_left"] == 10
    @test applied["entangler"]["lane_counts"]["flow2_r2_right_r3"] == 10
    @test applied["entangler"]["lane_counts"]["total"] == 30
    @test !haskey(derived, "attempt_time_s")
    @test !haskey(derived, "attempt_cap_hz")

    summary = SeQUeNCeQSavoryComparison._qsavory_summary_row(
        "qsavory_exact",
        3,
        10.0,
        [
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.5, "fidelity" => 0.9),
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.3, "fidelity" => 0.8),
            Dict{String,Any}("flow" => "flow1", "delivery_time_s" => 0.2, "fidelity" => 0.7),
        ],
        2,
    )
    @test summary["simulator"] == "qsavory_exact"
    @test summary["completion_time_s"] == 0.5
    @test summary["target_pairs"] == 2
    @test summary["target_completed"] == true
    @test summary["flow2_mean_fidelity"] ≈ 0.85

    partial_summary = SeQUeNCeQSavoryComparison._qsavory_summary_row(
        "qsavory_exact",
        4,
        10.0,
        [Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.3, "fidelity" => 0.8)],
        2,
    )
    @test partial_summary["completion_time_s"] == 0.3
    @test partial_summary["target_pairs"] == 2
    @test partial_summary["target_completed"] == false

    purified_summary = SeQUeNCeQSavoryComparison._qsavory_summary_row(
        "qsavory_exact",
        5,
        10.0,
        [
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.1, "fidelity" => 0.9, "status" => "ENTANGLED"),
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.2, "fidelity" => 0.95, "status" => "PURIFIED"),
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.3, "fidelity" => 0.96, "status" => "PURIFIED"),
        ],
        2,
        true,
    )
    @test purified_summary["flow2_delivered"] == 3
    @test purified_summary["target_completed"] == true
    @test purified_summary["completion_time_s"] == 0.2
    @test purified_summary["flow2_mean_fidelity"] ≈ (0.9 + 0.95 + 0.96) / 3

    unpurified_summary = SeQUeNCeQSavoryComparison._qsavory_summary_row(
        "qsavory_exact",
        6,
        10.0,
        [
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.1, "fidelity" => 0.9, "status" => "ENTANGLED"),
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.2, "fidelity" => 0.95, "status" => "PURIFIED"),
            Dict{String,Any}("flow" => "flow2", "delivery_time_s" => 0.3, "fidelity" => 0.91, "status" => "ENTANGLED"),
        ],
        3,
        true,
    )
    @test unpurified_summary["flow2_delivered"] == 3
    @test unpurified_summary["target_completed"] == false
    @test unpurified_summary["completion_time_s"] == ""
end

function _werner_cases()
    cases = Dict{String,Any}()
    for raw_line in readlines(joinpath(@__DIR__, "..", "tests", "werner_protocol_cases.toml"))
        line = strip(raw_line)
        (isempty(line) || startswith(line, "#")) && continue
        key, raw_value = strip.(split(line, "=", limit=2))
        if startswith(raw_value, "[")
            items = split(strip(raw_value, ['[', ']']), ",")
            cases[key] = [parse(Float64, strip(item)) for item in items if !isempty(strip(item))]
        else
            cases[key] = parse(Float64, raw_value)
        end
    end
    return cases
end
_werner_fidelity(w) = (3w + 1) / 4
_werner_from_fidelity(fidelity) = (4fidelity - 1) / 3
_bbpssw_werner_parameter(w) = 2w * (1 + 2w) / (3 * (1 + w^2))

function _phi_plus_fidelity(slot_a, slot_b)
    tensor = getfield(QS, Symbol("⊗"))
    bell = (tensor(QS.Z₁, QS.Z₁) + tensor(QS.Z₂, QS.Z₂)) / sqrt(2)
    return real(QS.observable((slot_a, slot_b), QS.SProjector(bell)))
end

@testset "QuantumSavory Werner protocol transforms" begin
    cases = _werner_cases()
    atol = cases["atol"]

    @testset "swapping squares Werner parameter" begin
        for w in cases["w_values"]
            net = QS.RegisterNet([QS.Register(1), QS.Register(2), QS.Register(1)])
            sim = QS.get_time_tracker(net)
            left_pair_id = 101
            right_pair_id = 202

            QS.initialize!((net[1][1], net[2][1]), QS.DepolarizedBellPair(w))
            QS.initialize!((net[2][2], net[3][1]), QS.DepolarizedBellPair(w))
            QS.tag!(net[1][1], QS.EntanglementCounterpart, 2, 1, left_pair_id)
            QS.tag!(net[2][1], QS.EntanglementCounterpart, 1, 1, left_pair_id)
            QS.tag!(net[2][2], QS.EntanglementCounterpart, 3, 1, right_pair_id)
            QS.tag!(net[3][1], QS.EntanglementCounterpart, 2, 2, right_pair_id)

            for node in 1:3
                QS.@process QS.EntanglementTracker(sim, net, node)()
            end
            QS.@process QS.SwapperProt(sim, net, 2; nodeL=1, nodeH=3, rounds=1, retry_lock_time=0.01, local_busy_time=0.0)()
            QS.run(sim, 1.0)

            result = QS.query(net[1], QS.EntanglementCounterpart, 3, 1, QS.❓; locked=false, assigned=true)
            @test !isnothing(result)
            output_w = _werner_from_fidelity(_phi_plus_fidelity(net[1][1], net[3][1]))
            @test output_w ≈ w^2 atol=atol
        end
    end

    @testset "BBPSSW matches Werner recurrence" begin
        for w in cases["w_values"]
            expected_w = _bbpssw_werner_parameter(w)
            success = false
            output_w = NaN

            for attempt in 1:200
                net = QS.RegisterNet([QS.Register(2), QS.Register(2)])
                sim = QS.get_time_tracker(net)
                QS.initialize!((net[1][1], net[2][1]), QS.DepolarizedBellPair(w))
                QS.initialize!((net[1][2], net[2][2]), QS.DepolarizedBellPair(w))
                QS.tag!(net[1][1], QS.EntanglementCounterpart, 2, 1, 101)
                QS.tag!(net[2][1], QS.EntanglementCounterpart, 1, 1, 101)
                QS.tag!(net[1][2], QS.EntanglementCounterpart, 2, 2, 202)
                QS.tag!(net[2][2], QS.EntanglementCounterpart, 1, 2, 202)

                QS.@process QS.BBPSSWProt(sim, net, 1, 2; rounds=1, retry_lock_time=0.01, tag=nothing)()
                QS.run(sim, 1.0)

                remaining = QS.queryall(net[1], QS.EntanglementCounterpart, 2, QS.❓, QS.❓; locked=false, assigned=true)
                if length(remaining) == 1
                    slot_a = remaining[1].slot
                    slot_b = net[2][remaining[1].tag[3]]
                    output_w = _werner_from_fidelity(_phi_plus_fidelity(slot_a, slot_b))
                    success = true
                    break
                end
            end

            @test success
            @test output_w ≈ expected_w atol=atol
            @test output_w > w
        end
    end

    @testset "BBPSSW candidates are end-to-end only" begin
        net = QS.RegisterNet([QS.Register(4), QS.Register(4), QS.Register(4)])
        sim = QS.get_time_tracker(net)
        pair_id = 100

        for (a, b, node_a, node_b) in (
            (net[1][1], net[2][1], 1, 2),
            (net[1][2], net[2][2], 1, 2),
            (net[2][3], net[3][1], 2, 3),
            (net[2][4], net[3][2], 2, 3),
            (net[1][3], net[3][3], 1, 3),
            (net[1][4], net[3][4], 1, 3),
        )
            QS.initialize!((a, b), QS.DepolarizedBellPair(1.0))
            QS.tag!(a, QS.EntanglementCounterpart, node_b, b.idx, pair_id)
            QS.tag!(b, QS.EntanglementCounterpart, node_a, a.idx, pair_id)
            pair_id += 1
        end

        observed_candidate_count = Ref(0)
        function choose_first_two(pairs)
            observed_candidate_count[] = length(pairs)
            @test length(pairs) == 2
            @test all(pair[1].tag[2] == 3 for pair in pairs)
            @test all(pair[2].tag[2] == 1 for pair in pairs)
            return (pairs[1], pairs[2])
        end

        QS.@process QS.BBPSSWProt(sim, net, 1, 3; rounds=1, retry_lock_time=0.01, choose_pairs=choose_first_two)()
        QS.run(sim, 1.0)

        @test observed_candidate_count[] == 2
        @test length(QS.queryall(net[1], QS.DistilledTag; assigned=true, locked=false)) == 1
        @test isempty(QS.queryall(net[2], QS.DistilledTag; assigned=true, locked=false))
        @test length(QS.queryall(net[3], QS.DistilledTag; assigned=true, locked=false)) == 1
    end
end

if get(ENV, "RUN_SLOW_SIM_TESTS", "0") == "1"
    @testset "optional elementary QuantumSavory validation" begin
        cfg_path = joinpath(@__DIR__, "..", "configs", "default.toml")
        cfg = load_config(cfg_path)
        trials = parse(Int, get(ENV, "ELEMENTARY_TEST_TRIALS", "300"))
        theory = elementary_rate_theory(cfg)
        timeout_s = parse(Float64, get(ENV, "ELEMENTARY_TEST_TIMEOUT_S", string(20 / theory["expected_rate_hz"])))
        for raw_state_model in ("exact", "werner")
            rows = run_qsavory_elementary_trials(cfg_path; seed=101, trials, timeout_s, raw_state_model)
            successes = [row for row in rows if row["success"]]

            @test length(successes) == trials
            @test all(row["simulator"] == "qsavory_$raw_state_model" for row in successes)
            completion_times = Float64[row["completion_time_s"] for row in successes]
            lo, hi = SeQUeNCeQSavoryComparison._mean_acceptance_interval(completion_times)
            @test lo <= theory["expected_mean_completion_time_s"] <= hi
            for row in successes
                @test row["fidelity"] ≈ theory["expected_raw_fidelity"] atol=1e-12
                @test 0 < row["completion_time_s"] <= timeout_s
            end
        end
    end
end
