"""
Edge cases the scanner should handle gracefully.
Some calls are extractable, some should produce warnings.
"""
from business_use import ensure


# 1. Normal — extractable
ensure(
    id="normal_node",
    flow="edge_cases",
    run_id="run_1",
    data={},
)

# 2. Dynamic id — NOT extractable, should warn
node_id = "dynamic_" + str(time.time())
ensure(
    id=node_id,
    flow="edge_cases",
    run_id="run_1",
    data={},
)

# 3. f-string id — NOT extractable, should warn
stage = "prod"
ensure(
    id=f"dynamic_{stage}",
    flow="edge_cases",
    run_id="run_1",
    data={},
)

# 4. dep_ids with mixed literals and variables — partial extraction, should warn
extra_dep = "some_other_node"
ensure(
    id="mixed_deps",
    flow="edge_cases",
    run_id="run_1",
    data={},
    dep_ids=["normal_node", extra_dep],
)

# 5. Conditional ensure — extractable (scanner doesn't care about control flow)
if feature_flags.new_checkout:
    ensure(
        id="conditional_node",
        flow="edge_cases",
        run_id="run_1",
        data={},
        dep_ids=["normal_node"],
    )
