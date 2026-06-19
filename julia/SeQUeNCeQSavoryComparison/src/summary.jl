function _mean_fidelity(rows)
    values = [row["fidelity"] for row in rows if row["fidelity"] != ""]
    return isempty(values) ? "" : mean(values)
end

function _qsavory_summary_row(simulator_label, seed, runtime_s, pairs, target_pairs, require_purified_flow2=false)
    flow1_rows = [row for row in pairs if row["flow"] == "flow1"]
    observed_flow2_rows = [row for row in pairs if row["flow"] == "flow2"]
    purified_flow2_rows = [row for row in observed_flow2_rows if get(row, "status", "") == "PURIFIED"]
    completion = ""
    if require_purified_flow2
        required_purified = max(target_pairs - 1, 0)
        target_completed = length(observed_flow2_rows) >= target_pairs && length(purified_flow2_rows) >= required_purified
        if target_completed
            flow2_times = sort(Float64[row["delivery_time_s"] for row in observed_flow2_rows])
            purified_times = sort(Float64[row["delivery_time_s"] for row in purified_flow2_rows])
            completion = flow2_times[target_pairs]
            if required_purified > 0
                completion = max(completion, purified_times[required_purified])
            end
        end
    else
        target_completed = length(observed_flow2_rows) >= target_pairs
        if !isempty(observed_flow2_rows)
            times = sort(Float64[row["delivery_time_s"] for row in observed_flow2_rows])
            completion = times[min(target_pairs, length(times))]
        end
    end
    return Dict{String,Any}(
        "simulator" => simulator_label,
        "seed" => seed,
        "status" => "completed",
        "runtime_s" => runtime_s,
        "completion_time_s" => completion,
        "target_pairs" => target_pairs,
        "target_completed" => target_completed,
        "flow1_delivered" => length(flow1_rows),
        "flow2_delivered" => length(observed_flow2_rows),
        "flow1_mean_fidelity" => _mean_fidelity(flow1_rows),
        "flow2_mean_fidelity" => _mean_fidelity(observed_flow2_rows),
    )
end
