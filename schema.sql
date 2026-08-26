-- AIPI PostgreSQL 16 Schema DDL
-- Generated from aipi.models (SQLAlchemy 2.0)

CREATE TABLE dgca_reference (
	id SERIAL NOT NULL, 
	period VARCHAR(7) NOT NULL, 
	route_code VARCHAR(16) NOT NULL, 
	avg_fare FLOAT NOT NULL, 
	passengers FLOAT, 
	source_note VARCHAR(256) NOT NULL, 
	is_placeholder BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_dgca_reference UNIQUE (period, route_code)
);

CREATE TABLE pipeline_run (
	run_id VARCHAR(16) NOT NULL, 
	code_version VARCHAR(32) NOT NULL, 
	git_sha VARCHAR(64) NOT NULL, 
	config_hash VARCHAR(64) NOT NULL, 
	input_row_count INTEGER NOT NULL, 
	index_eligible_rows INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (run_id)
);

CREATE TABLE route (
	route_code VARCHAR(16) NOT NULL, 
	origin VARCHAR(4) NOT NULL, 
	destination VARCHAR(4) NOT NULL, 
	display_name VARCHAR(64) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (route_code)
);

CREATE TABLE window_config (
	advance_days SERIAL NOT NULL, 
	is_extended BOOLEAN NOT NULL, 
	booking_weight FLOAT, 
	note VARCHAR(128) NOT NULL, 
	PRIMARY KEY (advance_days)
);

CREATE TABLE index_value (
	id SERIAL NOT NULL, 
	series VARCHAR(48) NOT NULL, 
	freq VARCHAR(8) NOT NULL, 
	index_date DATE NOT NULL, 
	value FLOAT NOT NULL, 
	n_obs INTEGER NOT NULL, 
	matched_n INTEGER NOT NULL, 
	coverage_pct FLOAT NOT NULL, 
	base_period_start DATE, 
	base_period_end DATE, 
	revision INTEGER NOT NULL, 
	is_current BOOLEAN NOT NULL, 
	published_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	pipeline_run_id VARCHAR(16) NOT NULL, 
	real_data_share FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_index_value_vintage UNIQUE (series, freq, index_date, revision), 
	CONSTRAINT ck_index_value_freq CHECK (freq IN ('daily', 'weekly', 'monthly')), 
	FOREIGN KEY(pipeline_run_id) REFERENCES pipeline_run (run_id)
);

CREATE TABLE observation (
	id SERIAL NOT NULL, 
	capture_date DATE NOT NULL, 
	capture_ts TIMESTAMP WITH TIME ZONE NOT NULL, 
	travel_date DATE NOT NULL, 
	advance_days INTEGER NOT NULL, 
	route_code VARCHAR(16) NOT NULL, 
	origin VARCHAR(4) NOT NULL, 
	destination VARCHAR(4) NOT NULL, 
	carrier VARCHAR(4) NOT NULL, 
	flight_no VARCHAR(12) NOT NULL, 
	brand_family VARCHAR(16) NOT NULL, 
	booking_class VARCHAR(4) NOT NULL, 
	cabin VARCHAR(16) NOT NULL, 
	total_fare FLOAT, 
	base_fare FLOAT, 
	taxes FLOAT, 
	udf_fee FLOAT, 
	convenience_fee FLOAT, 
	fees FLOAT, 
	currency VARCHAR(3) NOT NULL, 
	item_key VARCHAR(64) NOT NULL, 
	source VARCHAR(24) NOT NULL, 
	data_mode VARCHAR(16) NOT NULL, 
	is_soldout BOOLEAN NOT NULL, 
	is_outlier BOOLEAN NOT NULL, 
	in_index_slot BOOLEAN NOT NULL, 
	split_is_imputed BOOLEAN NOT NULL, 
	pipeline_run_id VARCHAR(16), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_observation_offer UNIQUE (capture_date, origin, destination, travel_date, advance_days, carrier, flight_no, brand_family, booking_class), 
	CONSTRAINT ck_observation_data_mode CHECK (data_mode IN ('real', 'synthetic')), 
	CONSTRAINT ck_observation_components_sum CHECK (total_fare IS NULL OR base_fare IS NULL OR taxes IS NULL OR ABS(COALESCE(base_fare,0) + COALESCE(taxes,0) + COALESCE(udf_fee,0) + COALESCE(convenience_fee,0) + COALESCE(fees,0) - total_fare) <= 1.0), 
	FOREIGN KEY(pipeline_run_id) REFERENCES pipeline_run (run_id)
);

CREATE TABLE route_weight (
	id SERIAL NOT NULL, 
	base_period VARCHAR(16) NOT NULL, 
	route_code VARCHAR(16) NOT NULL, 
	passengers FLOAT NOT NULL, 
	base_avg_fare FLOAT NOT NULL, 
	weight FLOAT NOT NULL, 
	source_note VARCHAR(256) NOT NULL, 
	is_placeholder BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_route_weight UNIQUE (base_period, route_code), 
	FOREIGN KEY(route_code) REFERENCES route (route_code)
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_observation_cell ON observation (route_code, advance_days, capture_date);
CREATE INDEX IF NOT EXISTS ix_observation_item ON observation (item_key, capture_date);
CREATE INDEX IF NOT EXISTS ix_index_value_current ON index_value (series, freq, index_date, is_current);
