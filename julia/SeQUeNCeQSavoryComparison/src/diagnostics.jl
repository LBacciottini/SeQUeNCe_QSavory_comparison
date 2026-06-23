const DIAGNOSTIC_SCHEMA_VERSION = 1
const DIAGNOSTIC_SCENARIOS = Set([
    "single_lane_elementary",
    "same_link_multilane",
    "competing_flows_same_bsm",
    "two_link_no_swap",
    "eg_swap_no_purification",
    "full_reduced",
])

function _diagnostic_scenario_config(cfg, scenario)
    scenario in DIAGNOSTIC_SCENARIOS || throw(ArgumentError("unknown diagnostic scenario $scenario"))
    out = deepcopy(cfg)
    flow1 = out["resource_reservation"]["flow1"]
    flow2 = out["resource_reservation"]["flow2"]
    if scenario == "single_lane_elementary"
        flow1["target_pairs"] = 1
        flow1["r1_slots"] = [0, 0]
        flow1["r2_slots"] = [0, 0]
        flow2["target_pairs"] = 0
        out["purification"]["enabled"] = false
    elseif scenario == "same_link_multilane"
        flow1["target_pairs"] = min(10, Int(flow1["r1_slots"][2]) - Int(flow1["r1_slots"][1]) + 1)
        flow2["target_pairs"] = 0
        out["purification"]["enabled"] = false
    elseif scenario == "competing_flows_same_bsm"
        flow2["target_pairs"] = 0
        out["purification"]["enabled"] = false
    elseif scenario == "two_link_no_swap"
        flow1["target_pairs"] = 0
        flow2["target_pairs"] = 0
        out["purification"]["enabled"] = false
    elseif scenario == "eg_swap_no_purification"
        flow1["target_pairs"] = 0
        flow2["target_pairs"] = min(10, Int(flow2["r1_slots"][2]) - Int(flow2["r1_slots"][1]) + 1)
        out["purification"]["enabled"] = false
    elseif scenario == "full_reduced"
        flow2["target_pairs"] = min(2, Int(flow2["r1_slots"][2]) - Int(flow2["r1_slots"][1]) + 1)
    end
    return out
end

function _diagnostic_event(simulator, seed, scenario, link_length_km; flow="", link="", node="", slot="", stage, event, time_s, pair_id="", details="{}")
    return Dict{String,Any}(
        "simulator" => simulator,
        "seed" => seed,
        "link_length_km" => link_length_km,
        "scenario" => scenario,
        "flow" => flow,
        "link" => link,
        "node" => node,
        "slot" => slot,
        "stage" => stage,
        "event" => event,
        "time_s" => time_s,
        "pair_id" => pair_id,
        "details_json" => details,
    )
end

function _diagnostic_events_from_pairs(pairs, simulator, seed, scenario, link_length_km)
    rows = Vector{Dict{String,Any}}()
    for pair in pairs
        flow = pair["flow"]
        link = "$(pair["local_node"])-$(pair["remote_node"])"
        details = "{\"fidelity\":$(pair["fidelity"]),\"status\":\"$(get(pair, "status", ""))\"}"
        push!(rows, _diagnostic_event(
            simulator,
            seed,
            scenario,
            link_length_km;
            flow,
            link,
            node=pair["local_node"],
            slot=pair["local_slot"],
            stage="pair",
            event="delivered",
            time_s=pair["delivery_time_s"],
            pair_id=pair["pair_id"],
            details,
        ))
        if flow == "flow2"
            push!(rows, _diagnostic_event(simulator, seed, scenario, link_length_km; flow, link="r1-r3", node=pair["local_node"], slot=pair["local_slot"], stage="swapped_delivered", event="delivered", time_s=pair["delivery_time_s"], pair_id=pair["pair_id"], details))
            if get(pair, "status", "") == "PURIFIED"
                push!(rows, _diagnostic_event(simulator, seed, scenario, link_length_km; flow, link="r1-r3", node=pair["local_node"], slot=pair["local_slot"], stage="bbpssw_completed", event="completed", time_s=pair["delivery_time_s"], pair_id=pair["pair_id"], details))
            end
        end
    end
    return rows
end

function _diagnostic_elementary_events(net, resolved, simulator, seed, scenario, link_length_km)
    flow1 = resolved["resource_reservation"]["flow1"]
    flow2 = resolved["resource_reservation"]["flow2"]
    rows = Vector{Dict{String,Any}}()
    append!(rows, _diagnostic_elementary_events_for_link(net, simulator, seed, scenario, link_length_km, 1, 2, flow1["r1_slots"], "flow1", "r1-r2"))
    append!(rows, _diagnostic_elementary_events_for_link(net, simulator, seed, scenario, link_length_km, 1, 2, flow2["r1_slots"], "flow2_left", "r1-r2"))
    append!(rows, _diagnostic_elementary_events_for_link(net, simulator, seed, scenario, link_length_km, 2, 3, flow2["r2_right_slots"], "flow2_right", "r2-r3"))
    return rows
end

function _diagnostic_elementary_events_for_link(net, simulator, seed, scenario, link_length_km, nodeA, nodeB, slotrange, flow, link)
    rows = Vector{Dict{String,Any}}()
    lower = Int(slotrange[1]) + 1
    upper = Int(slotrange[2]) + 1
    for result in queryall(net[nodeA], EntanglementCounterpart, nodeB, W, W; locked=false, assigned=true)
        lower <= result.slot.idx <= upper || continue
        details = "{\"remote_node\":$(nodeB),\"remote_slot\":$(result.tag[3])}"
        push!(rows, _diagnostic_event(simulator, seed, scenario, link_length_km; flow, link, node="r$(nodeA)", slot=result.slot.idx, stage="elementary_delivered", event="delivered", time_s=result.time, pair_id=string(result.tag[4]), details))
    end
    return rows
end

function _summarize_diagnostic_events(events)
    groups = Dict{Tuple,Vector{Float64}}()
    for row in events
        time = get(row, "time_s", "")
        time == "" && continue
        key = (
            get(row, "simulator", ""),
            get(row, "seed", ""),
            get(row, "scenario", ""),
            get(row, "link_length_km", ""),
            get(row, "stage", ""),
            get(row, "event", ""),
        )
        push!(get!(groups, key, Float64[]), Float64(time))
    end
    rows = Vector{Dict{String,Any}}()
    for key in sort(collect(keys(groups)); by=string)
        times = sort(groups[key])
        intervals = diff(times)
        push!(rows, Dict{String,Any}(
            "simulator" => key[1],
            "seed" => key[2],
            "scenario" => key[3],
            "link_length_km" => key[4],
            "stage" => key[5],
            "event" => key[6],
            "count" => length(times),
            "first_time_s" => first(times),
            "nth_time_s" => last(times),
            "mean_interarrival_s" => isempty(intervals) ? "" : mean(intervals),
            "mean_duration_s" => "",
        ))
    end
    return rows
end

"""
    run_qsavory_diagnostic(config_path, seed, output_dir; scenario, raw_state_model="exact")

Run a QuantumSavory diagnostic scenario and write `events.csv`,
`stage_summary.csv`, and `diagnostic_manifest.json`.
"""
function run_qsavory_diagnostic(config_path::AbstractString, seed::Integer, output_dir::AbstractString; scenario::AbstractString, raw_state_model="exact")
    cfg = _diagnostic_scenario_config(load_config(config_path), scenario)
    resolved = resolve_config(cfg)
    result = _run_qsavory_resolved(cfg, resolved, seed, output_dir; raw_state_model, diagnostic_scenario=scenario)
    simulator = result["summary"]["simulator"]
    link_length_km = Float64(resolved["topology"]["link_length_km"])
    events = _diagnostic_events_from_pairs(result["pairs"], simulator, seed, scenario, link_length_km)
    append!(events, _diagnostic_elementary_events(result["net"], resolved, simulator, seed, scenario, link_length_km))
    stages = _summarize_diagnostic_events(events)
    manifest = Dict{String,Any}(
        "schema_version" => DIAGNOSTIC_SCHEMA_VERSION,
        "simulator" => simulator,
        "raw_state_model" => _normalize_raw_state_model(raw_state_model),
        "seed" => seed,
        "scenario" => scenario,
        "created_at" => string(now(UTC)),
        "raw_config" => cfg,
        "resolved_config" => resolved,
        "outputs" => Dict("events" => "events.csv", "stage_summary" => "stage_summary.csv", "manifest" => "diagnostic_manifest.json"),
    )
    _write_diagnostic_events_csv(joinpath(output_dir, "events.csv"), events)
    _write_diagnostic_stage_csv(joinpath(output_dir, "stage_summary.csv"), stages)
    write_json(joinpath(output_dir, "diagnostic_manifest.json"), manifest)
    return Dict("manifest" => manifest, "events" => events, "stage_summary" => stages, "pairs" => result["pairs"], "summary" => result["summary"])
end
