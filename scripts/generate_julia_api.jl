using SeQUeNCeQSavoryComparison

const QS = SeQUeNCeQSavoryComparison

function _slug(value)
    chars = Char[]
    previous_dash = false
    for char in lowercase(String(value))
        if isletter(char) || isdigit(char)
            push!(chars, char)
            previous_dash = false
        elseif !previous_dash
            push!(chars, '-')
            previous_dash = true
        end
    end
    return strip(String(chars), ['-'])
end

function _render_template(template_path, values)
    rendered = read(template_path, String)
    for (key, value) in values
        rendered = replace(rendered, "{{$(key)}}" => value)
    end
    return rstrip(rendered) * "\n"
end

function _docstring_text(name::Symbol, object)
    binding = Docs.Binding(QS, name)
    doc = Docs.doc(binding)
    text = sprint(show, MIME("text/plain"), doc)
    if occursin("No documentation found", text)
        doc = Docs.doc(object)
        text = sprint(show, MIME("text/plain"), doc)
    end
    return strip(text)
end

function _escape_autoref_brackets(text)
    replace(text, "[" => "\\[", "]" => "\\]")
end

function main(args)
    output = length(args) >= 1 ? args[1] : "docs/generated/api/julia.md"
    template = length(args) >= 2 ? args[2] : "scripts/templates/api_page.md.tmpl"
    mkpath(dirname(output))
    exported = sort!(String.(names(QS; all=false, imported=false)))

    index = String[]
    body = String[]
    for name in exported
        anchor = "symbol-" * _slug(name)
        push!(index, "- [`$name`](#$anchor)")
        push!(body, """<a id="$anchor"></a>""")
        push!(body, "## `$name`")
        push!(body, "")
        object = getfield(QS, Symbol(name))
        doc = _docstring_text(Symbol(name), object)
        if isempty(doc) || occursin("No documentation found", doc)
            push!(body, "!!! warning \"Missing docstring\"")
            push!(body, "    No docstring is currently available for this exported symbol.")
        else
            push!(body, _escape_autoref_brackets(doc))
        end
        push!(body, "")
    end

    rendered = _render_template(template, Dict(
        "title" => "Julia API",
        "language" => "Julia",
        "source_summary" => "Exported docstrings from `SeQUeNCeQSavoryComparison`.",
        "intro" => "The Julia API page is generated from exported package symbols using `scripts/generate_julia_api.jl`.",
        "index" => join(index, "\n"),
        "body" => rstrip(join(body, "\n")),
    ))
    write(output, rendered)
end

main(ARGS)
