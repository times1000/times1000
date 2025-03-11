-- Migration script to update the database schema for the unified agent model

-- Add new columns to agents table (supports both MySQL and MariaDB syntax)
-- First check if the columns exist
DROP PROCEDURE IF EXISTS add_agent_columns;

DELIMITER //
CREATE PROCEDURE add_agent_columns()
BEGIN
    DECLARE personality_exists INT;
    DECLARE settings_exists INT;
    
    SELECT COUNT(*) INTO personality_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agents' AND COLUMN_NAME = 'personality_profile';
    
    SELECT COUNT(*) INTO settings_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agents' AND COLUMN_NAME = 'settings';
    
    -- Add personality_profile if it doesn't exist
    IF personality_exists = 0 THEN
        ALTER TABLE agents ADD COLUMN personality_profile TEXT NULL;
    END IF;
    
    -- Add settings if it doesn't exist
    IF settings_exists = 0 THEN
        ALTER TABLE agents ADD COLUMN settings JSON NULL;
    END IF;
END //
DELIMITER ;

CALL add_agent_columns();
DROP PROCEDURE IF EXISTS add_agent_columns;

-- Add missing details column to plan_steps if it doesn't exist
DROP PROCEDURE IF EXISTS add_details_column;

DELIMITER //
CREATE PROCEDURE add_details_column()
BEGIN
    DECLARE details_exists INT;
    
    SELECT COUNT(*) INTO details_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'plan_steps' AND COLUMN_NAME = 'details';
    
    -- Add details column if it doesn't exist
    IF details_exists = 0 THEN
        ALTER TABLE plan_steps ADD COLUMN details TEXT NULL;
    END IF;
END //
DELIMITER ;

CALL add_details_column();
DROP PROCEDURE IF EXISTS add_details_column;

-- Create a procedure to handle type migration
DROP PROCEDURE IF EXISTS migrate_agent_types;

DELIMITER //
CREATE PROCEDURE migrate_agent_types()
BEGIN
    -- Check if type column exists 
    DECLARE type_exists INT;
    
    SELECT COUNT(*) INTO type_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'agents' AND COLUMN_NAME = 'type';
    
    -- If the type column still exists, migrate data to settings
    IF type_exists > 0 THEN
        -- Update settings column to include the previous type
        UPDATE agents
        SET settings = JSON_OBJECT('former_type', type);
        
        -- Now drop the type column
        ALTER TABLE agents DROP COLUMN type;
        
        SELECT 'Migration of agent types to settings completed successfully.' AS result;
    ELSE
        SELECT 'No migration needed: type column already removed.' AS result;
    END IF;
END //
DELIMITER ;

-- Execute the migration
CALL migrate_agent_types();

-- Drop the procedure
DROP PROCEDURE IF EXISTS migrate_agent_types;

-- Update database so it can accept numeric durations
DROP PROCEDURE IF EXISTS update_duration_column;

DELIMITER //
CREATE PROCEDURE update_duration_column()
BEGIN
    DECLARE column_type VARCHAR(100);
    
    -- Check the column type
    SELECT DATA_TYPE INTO column_type
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = 'plan_steps' 
      AND COLUMN_NAME = 'estimated_duration';
    
    -- Only modify if it's not already an INT
    IF column_type != 'int' THEN
        -- First convert any non-numeric values to a default value to avoid truncation errors
        UPDATE plan_steps SET estimated_duration = '60' WHERE estimated_duration NOT REGEXP '^[0-9]+$';
        
        -- Now modify the column type
        ALTER TABLE plan_steps MODIFY COLUMN estimated_duration INT NULL;
    END IF;
END //
DELIMITER ;

CALL update_duration_column();
DROP PROCEDURE IF EXISTS update_duration_column;