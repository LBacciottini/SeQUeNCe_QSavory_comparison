_json_escape(s::AbstractString) = replace(replace(replace(replace(s, "\\" => "\\\\"), "\"" => "\\\""), "\n" => "\\n"), "\r" => "\\r")
_csv_cell(value) = begin
    text = string(value)
    if occursin(",", text) || occursin("\"", text) || occursin("\n", text) || occursin("\r", text)
        return "\"" * replace(text, "\"" => "\"\"") * "\""
    end
    return text
end

function _json(io, value)
    if value === nothing
        print(io, "null")
    elseif value isa Bool
        print(io, value ? "true" : "false")
    elseif value isa Integer || value isa AbstractFloat
        print(io, value)
    elseif value isa AbstractString
        print(io, '"', _json_escape(value), '"')
    elseif value isa AbstractDict
        print(io, "{")
        first = true
        for key in sort!(collect(keys(value)); by=string)
            first || print(io, ",")
            first = false
            _json(io, string(key)); print(io, ":"); _json(io, value[key])
        end
        print(io, "}")
    elseif value isa AbstractVector || value isa Tuple
        print(io, "[")
        for (i, item) in enumerate(value)
            i == 1 || print(io, ",")
            _json(io, item)
        end
        print(io, "]")
    else
        _json(io, string(value))
    end
end

function write_json(path, value)
    open(path, "w") do io
        _json(io, value)
        println(io)
    end
end

function _write_pairs_csv(path, rows)
    fields = ["simulator", "seed", "flow", "local_node", "local_slot", "remote_node", "remote_slot", "pair_id", "delivery_time_s", "fidelity", "status"]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([_csv_cell(get(row, field, "")) for field in fields], ","))
        end
    end
end

function _write_summary_csv(path, rows)
    fields = ["simulator", "seed", "status", "runtime_s", "completion_time_s", "target_pairs", "target_completed", "flow1_delivered", "flow2_delivered", "flow1_mean_fidelity", "flow2_mean_fidelity"]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([_csv_cell(get(row, field, "")) for field in fields], ","))
        end
    end
end

function _write_elementary_validation_csv(path, rows)
    fields = [
        "simulator", "seed", "trial", "success", "completion_time_s",
        "timeout_s", "effective_attempt_time_s", "success_probability", "round2_entry_probability",
        "round1_time_s", "round2_time_s", "expected_rate_hz",
        "fidelity", "expected_fidelity",
    ]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([_csv_cell(get(row, field, "")) for field in fields], ","))
        end
    end
end

function _write_diagnostic_events_csv(path, rows)
    fields = [
        "simulator", "seed", "link_length_km", "scenario", "flow", "link",
        "node", "slot", "stage", "event", "time_s", "pair_id", "details_json",
    ]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([_csv_cell(get(row, field, "")) for field in fields], ","))
        end
    end
end

function _write_diagnostic_stage_csv(path, rows)
    fields = [
        "simulator", "seed", "scenario", "link_length_km", "stage", "event",
        "count", "first_time_s", "nth_time_s", "mean_interarrival_s", "mean_duration_s",
    ]
    open(path, "w") do io
        println(io, join(fields, ","))
        for row in rows
            println(io, join([get(row, field, "") for field in fields], ","))
        end
    end
end
