-- MySQL 初始化腳本
-- 此腳本會在容器首次啟動時自動執行

-- 設定字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;

-- 確保資料庫使用正確的字符集
ALTER DATABASE kigurumi_db CHARACTER SET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- 顯示訊息
SELECT 'MySQL 資料庫初始化完成' AS message;
