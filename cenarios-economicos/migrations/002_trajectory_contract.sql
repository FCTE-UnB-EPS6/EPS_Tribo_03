CREATE TABLE IF NOT EXISTS economic_scenarios.trajectory_set (
    id text NOT NULL,
    version text NOT NULL,
    content jsonb NOT NULL,
    PRIMARY KEY (id, version)
);

ALTER TABLE economic_scenarios.run
    ALTER COLUMN assumption_id DROP NOT NULL,
    ALTER COLUMN assumption_version DROP NOT NULL;

ALTER TABLE economic_scenarios.run
    ADD COLUMN IF NOT EXISTS contract_version text NOT NULL DEFAULT '0.1.0',
    ADD COLUMN IF NOT EXISTS trajectory_id text,
    ADD COLUMN IF NOT EXISTS trajectory_version text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'run_trajectory_fk'
          AND conrelid = 'economic_scenarios.run'::regclass
    ) THEN
        ALTER TABLE economic_scenarios.run
            ADD CONSTRAINT run_trajectory_fk
            FOREIGN KEY (trajectory_id, trajectory_version)
            REFERENCES economic_scenarios.trajectory_set (id, version);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'run_input_identity_check'
          AND conrelid = 'economic_scenarios.run'::regclass
    ) THEN
        ALTER TABLE economic_scenarios.run
            ADD CONSTRAINT run_input_identity_check CHECK (
                (contract_version = '0.1.0'
                    AND assumption_id IS NOT NULL
                    AND assumption_version IS NOT NULL
                    AND trajectory_id IS NULL
                    AND trajectory_version IS NULL)
                OR
                (contract_version = '0.2.0'
                    AND assumption_id IS NULL
                    AND assumption_version IS NULL
                    AND trajectory_id IS NOT NULL
                    AND trajectory_version IS NOT NULL)
            );
    END IF;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgrelid = 'economic_scenarios.trajectory_set'::regclass
          AND tgname = 'reject_mutation'
    ) THEN
        CREATE TRIGGER reject_mutation
        BEFORE UPDATE OR DELETE ON economic_scenarios.trajectory_set
        FOR EACH ROW EXECUTE FUNCTION economic_scenarios.reject_mutation();
    END IF;
END;
$$;
