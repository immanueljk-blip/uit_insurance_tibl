-- Disable checks and safe update mode for the session
SET FOREIGN_KEY_CHECKS = 0;
SET SQL_SAFE_UPDATES = 0;

-- 1. Delete the new 113 active rows
DELETE FROM sales_commissions WHERE is_active = 1;
DELETE FROM commission_rates WHERE is_active = 1;
DELETE FROM claims WHERE is_active = 1;
DELETE FROM policies WHERE is_active = 1;
DELETE FROM products WHERE is_active = 1;
DELETE FROM backoffice_users WHERE is_active = 1;
DELETE FROM carriers WHERE is_active = 1;
DELETE FROM clients WHERE is_active = 1;

-- 2. Restore the 1,000 inactive rows to active status
UPDATE sales_commissions SET is_active = 1 WHERE is_active = 0;
UPDATE commission_rates SET is_active = 1 WHERE is_active = 0;
UPDATE claims SET is_active = 1 WHERE is_active = 0;
UPDATE policies SET is_active = 1 WHERE is_active = 0;
UPDATE products SET is_active = 1 WHERE is_active = 0;
UPDATE backoffice_users SET is_active = 1 WHERE is_active = 0;
UPDATE carriers SET is_active = 1 WHERE is_active = 0;
UPDATE clients SET is_active = 1 WHERE is_active = 0;

-- Re-enable checks and safe update mode
SET SQL_SAFE_UPDATES = 1;
SET FOREIGN_KEY_CHECKS = 1;


