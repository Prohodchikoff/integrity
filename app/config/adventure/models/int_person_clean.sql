SELECT
    person_id,
    first_name,
    middle_name,
    last_name,
    CONCAT(first_name, ' ', last_name) AS full_name,
    person_type,
    CASE 
        WHEN name_style = 1 THEN 'formal'
        ELSE 'informal'
    END AS name_style_label,
    modified_date
FROM {{ ref('stg_person') }}