SELECT *
FROM {{ relation }}
WHERE {{ column }} NOT IN ('EM', 'IN', 'SP', 'SC', 'VC', 'GC')
