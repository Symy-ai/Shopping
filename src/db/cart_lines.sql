create table cart_lines (
    id uuid primary key default gen_random_uuid(),
    user_ref text not null,
    product_ref text not null,
    title text not null,
    price_cents integer not null,
    currency text not null default 'USD',
    qty integer not null default 1,
    image_url text,
    updated_at timestamptz default now(),
    unique (user_ref, product_ref)
);
