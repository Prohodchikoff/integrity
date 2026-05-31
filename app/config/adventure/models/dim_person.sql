SELECT
    person_id,
    full_name,
    person_type,
    name_style_label,
    modified_date
FROM {{ ref('int_person_clean') }}