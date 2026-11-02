-- Executar somente num banco separado chamado pdv_robo.
-- Este script NAO deve ser executado no banco control do Arpa.
BEGIN;
DO $ BEGIN
  IF current_database() <> 'pdv_robo' THEN
    RAISE EXCEPTION 'Banco incorreto: esperado pdv_robo';
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS robot_events (
 id bigserial PRIMARY KEY,
 created_at timestamptz NOT NULL DEFAULT now(),
 event jsonb NOT NULL
);

COMMIT;
