CREATE TABLE IF not EXISTS frida_storage  (
   hash VARCHAR(255) PRIMARY KEY,
   book_name VARCHAR(255),
   title VARCHAR(255) NOT NULL,
   text TEXT NOT NULL,
   url VARCHAR(255), 
   isExstra BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF not EXISTS users (
   user_id BIGINT PRIMARY KEY, 
   username VARCHAR(255),
   first_name VARCHAR(255),
   last_name VARCHAR(255),
   date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
   is_admin BOOLEAN DEFAULT FALSE 
);

CREATE TABLE IF not EXISTS bot_logs (
   log_id SERIAL PRIMARY KEY,
   user_id BIGINT,
   query VARCHAR,
   response TEXT,
   response_status BOOLEAN,
   created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,           
   CONSTRAINT fk_user_id FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF not EXISTS bot_log_topic_hashes (
   log_id BIGINT,
   topic_hash VARCHAR(255),
   CONSTRAINT fk_log_id FOREIGN KEY (log_id) REFERENCES bot_logs(log_id) ON DELETE cascade ON UPDATE cascade,
   PRIMARY KEY (log_id, topic_hash)
);


create table IF not EXISTS exstraTopics(
	hash varchar(255) primary KEY,
	user_id BIGINT,
	constraint fk_user_id foreign key (user_id) references users(user_id) on delete cascade on update cascade,
	constraint fk_hash foreign key (hash) references frida_storage(hash) on delete cascade on update cascade
)