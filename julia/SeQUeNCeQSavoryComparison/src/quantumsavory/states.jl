_selector(range_pair) = slot -> Int(range_pair[1]) + 1 <= slot <= Int(range_pair[2]) + 1

function _normalize_raw_state_model(raw_state_model)
    model = lowercase(String(raw_state_model))
    model in ("exact", "werner") || throw(ArgumentError("raw_state_model must be 'exact' or 'werner', got '$raw_state_model'"))
    return model
end

_qsavory_simulator_label(model) = "qsavory_$(model)"

function _raw_pair_state(resolved, model)
    if model == "exact"
        return BarrettKokBellPair(
            resolved["derived"]["arm_transmissivity"],
            resolved["derived"]["arm_transmissivity"],
            Float64(resolved["detectors"]["dark_count_probability"]),
            Float64(resolved["detectors"]["efficiency"]),
            Float64(resolved["barrett_kok"]["mode_matching_visibility"]),
            Int(resolved["barrett_kok"]["parity_bit"]),
        )
    end
    return DepolarizedBellPair(; F=resolved["derived"]["barrett_kok_raw_fidelity"])
end

function _bell_fidelity(slot_a, slot_b, model, flow="flow1")
    bell = model == "exact" && flow == "flow1" ? (Z₁ ⊗ Z₂ + Z₂ ⊗ Z₁) / sqrt(2) : (Z₁ ⊗ Z₁ + Z₂ ⊗ Z₂) / sqrt(2)
    return real(observable((slot_a, slot_b), SProjector(bell)))
end

function _collect_qsavory_pairs(net, sim, seed, simulator_label, model)
    rows = Vector{Dict{String,Any}}()
    for (remote, flow) in ((2, "flow1"), (3, "flow2"))
        for result in queryall(net[1], EntanglementCounterpart, remote, W, W; locked=false, assigned=true)
            remote_slot = result.tag[3]
            fidelity = try
                _bell_fidelity(result.slot, net[remote][remote_slot], model, flow)
            catch
                ""
            end
            pair_status = !isnothing(query(result.slot, DistilledTag)) ? "PURIFIED" : "ENTANGLED"
            push!(rows, Dict{String,Any}(
                "simulator" => simulator_label,
                "seed" => seed,
                "flow" => flow,
                "local_node" => "r1",
                "local_slot" => result.slot.idx,
                "remote_node" => "r$remote",
                "remote_slot" => remote_slot,
                "pair_id" => string(result.tag[4]),
                "delivery_time_s" => result.time,
                "fidelity" => fidelity,
                "status" => pair_status,
            ))
        end
    end
    return rows
end
