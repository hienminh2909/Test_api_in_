-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.categories (
  id integer NOT NULL DEFAULT nextval('categories_id_seq'::regclass),
  category_name text NOT NULL UNIQUE,
  category_code text NOT NULL UNIQUE,
  description text,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT categories_pkey PRIMARY KEY (id)
);
CREATE TABLE public.devices (
  id integer NOT NULL DEFAULT nextval('devices_id_seq'::regclass),
  device_code text NOT NULL UNIQUE,
  device_name text NOT NULL,
  room_id integer,
  status text DEFAULT 'Bình thường'::text,
  created_at timestamp with time zone,
  last_inventory_at timestamp with time zone,
  barcode_url text,
  qr_url text,
  category_id integer,
  description text,
  image_url text,
  updated_at timestamp with time zone,
  purchase_date date,
  device_price text,
  created_by integer,
  CONSTRAINT devices_pkey PRIMARY KEY (id),
  CONSTRAINT devices_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id),
  CONSTRAINT devices_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id),
  CONSTRAINT devices_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);
CREATE TABLE public.inventory_logs (
  id integer NOT NULL DEFAULT nextval('inventory_logs_id_seq'::regclass),
  device_id integer,
  status_at_scan text,
  inventory_at timestamp with time zone DEFAULT now(),
  handheld_name text,
  CONSTRAINT inventory_logs_pkey PRIMARY KEY (id),
  CONSTRAINT inventory_logs_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id)
);
CREATE TABLE public.report_logs (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  reported_at timestamp with time zone NOT NULL DEFAULT now(),
  device_id integer,
  status text,
  note text,
  description text,
  handheld_name text,
  CONSTRAINT report_logs_pkey PRIMARY KEY (id),
  CONSTRAINT report_logs_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id)
);
CREATE TABLE public.requests (
  id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  device_id bigint,
  created_by bigint,
  reason text,
  status text DEFAULT '''''pending''''::text'::text,
  resolved_by integer,
  resolved_at timestamp without time zone,
  CONSTRAINT requests_pkey PRIMARY KEY (id),
  CONSTRAINT requests_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.devices(id),
  CONSTRAINT requests_resolved_by_fkey FOREIGN KEY (resolved_by) REFERENCES public.users(id),
  CONSTRAINT requests_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id)
);
CREATE TABLE public.rooms (
  id integer NOT NULL DEFAULT nextval('rooms_id_seq'::regclass),
  room_name text NOT NULL,
  description text,
  CONSTRAINT rooms_pkey PRIMARY KEY (id)
);
CREATE TABLE public.users (
  id integer NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  full_name text NOT NULL,
  username text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role text DEFAULT 'teacher'::text CHECK (role = ANY (ARRAY['admin'::text, 'teacher'::text])),
  created_at timestamp with time zone,
  room_id integer,
  phone numeric,
  email text,
  CONSTRAINT users_pkey PRIMARY KEY (id),
  CONSTRAINT users_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.rooms(id)
);