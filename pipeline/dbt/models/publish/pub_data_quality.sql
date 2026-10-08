{{ config(format='json', location='data_quality.json') }}
-- data_quality.json, the monthly lane's file for ourhike.org/data/quality/
-- (decision 102): every check this build ran, as counts and names, published
-- sources only. macros/data_quality.sql holds the SQL and says what is in the
-- file and why; pub_conditions_data_quality is the hourly lane's.
{{ data_quality_document('monthly') }}
