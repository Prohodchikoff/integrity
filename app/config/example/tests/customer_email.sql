SELECT *
FROM {{ relation }}
WHERE {{ column }} NOT LIKE '%@%'

