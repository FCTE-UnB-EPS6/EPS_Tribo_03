CREATE SCHEMA IF NOT EXISTS economic_scenarios;

CREATE TABLE IF NOT EXISTS economic_scenarios.assumption_set (
    id text NOT NULL,
    version text NOT NULL,
    content jsonb NOT NULL,
    PRIMARY KEY (id, version)
);
CREATE TABLE IF NOT EXISTS economic_scenarios.ruleset (
    id text NOT NULL,
    version text NOT NULL,
    content jsonb NOT NULL,
    PRIMARY KEY (id, version)
);
CREATE TABLE IF NOT EXISTS economic_scenarios.run (
    id uuid PRIMARY KEY,
    assumption_id text NOT NULL,
    assumption_version text NOT NULL,
    ruleset_id text NOT NULL,
    ruleset_version text NOT NULL,
    content jsonb NOT NULL,
    FOREIGN KEY (assumption_id, assumption_version)
        REFERENCES economic_scenarios.assumption_set (id, version),
    FOREIGN KEY (ruleset_id, ruleset_version)
        REFERENCES economic_scenarios.ruleset (id, version)
);
CREATE TABLE IF NOT EXISTS economic_scenarios.scenario (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES economic_scenarios.run (id),
    scenario_key text NOT NULL CHECK (scenario_key IN ('base', 'adverse', 'favorable')),
    content jsonb NOT NULL,
    UNIQUE (run_id, scenario_key)
);

CREATE OR REPLACE FUNCTION economic_scenarios.reject_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Economic scenario records are immutable';
END;
$$;
DO $$
DECLARE table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['assumption_set', 'ruleset', 'run', 'scenario']
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgrelid = format('economic_scenarios.%I', table_name)::regclass
              AND tgname = 'reject_mutation'
        ) THEN
            EXECUTE format('CREATE TRIGGER reject_mutation BEFORE UPDATE OR DELETE ON economic_scenarios.%I FOR EACH ROW EXECUTE FUNCTION economic_scenarios.reject_mutation()', table_name);
        END IF;
    END LOOP;
END;
$$;
