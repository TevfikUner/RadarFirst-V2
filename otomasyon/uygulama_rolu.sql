-- API ve işçinin bağlandığı süper kullanıcı OLMAYAN rol (bkz. otomasyon/uygulama_rolu_olustur.sh).
-- Rol yalnızca bu veritabanının ve tablolarının sahibidir: alembic migration'larını
-- çalıştırabilir, kendi tablolarına yazabilir; başka veritabanlarına, rollere,
-- sunucu dosyalarına (COPY ... PROGRAM, pg_read_file) erişemez. Tekrar çalıştırılabilir.
-- Değişkenler: :rol, :sifre (stdin'den \set ile verilir, komut satırına yazılmaz).
\set ON_ERROR_STOP on

SELECT format('CREATE ROLE %I LOGIN', :'rol')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'rol') \gexec

SELECT format(
  'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
  :'rol', :'sifre') \gexec

SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), :'rol') \gexec

-- Tablo sahipliği, tabloya bağlı dizileri (serial/identity) de taşır.
SELECT format('ALTER %s public.%I OWNER TO %I',
  CASE c.relkind WHEN 'v' THEN 'VIEW' WHEN 'm' THEN 'MATERIALIZED VIEW' ELSE 'TABLE' END, c.relname, :'rol')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm') AND pg_get_userbyid(c.relowner) <> :'rol' \gexec

SELECT format('ALTER SEQUENCE public.%I OWNER TO %I', c.relname, :'rol')
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'S' AND pg_get_userbyid(c.relowner) <> :'rol' \gexec

SELECT pg_get_userbyid(c.relowner) AS sahip, count(*) AS nesne
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' GROUP BY 1;
