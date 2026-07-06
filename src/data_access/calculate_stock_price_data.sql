WITH target_rows AS (
    SELECT stock_id, ticker_code
    FROM public.t_stock_original_price_data
    WHERE del_yn = false
      AND calculated_yn = false
),
     calculated AS (
         SELECT
             base.*,
             COUNT(close_price) OVER w20 AS cnt_20,
             COUNT(close_price) OVER w30 AS cnt_30,
             AVG(close_price) OVER w20 AS ma_20_calc,
             STDDEV(close_price) OVER w20 AS volatility_calc,
             close_price / MAX(high_price) OVER w30 - 1 AS dd_high_calc,
             close_price / MIN(low_price) OVER w30 - 1 AS ret_low_calc,
             close_price / LAG(close_price) OVER w_all - 1 AS daily_change
         FROM public.t_stock_original_price_data base
         WHERE base.del_yn = false
           AND base.ticker_code IN (
             SELECT ticker_code
             FROM target_rows
         )
         WINDOW
             w_all AS (
                     PARTITION BY ticker_code
                     ORDER BY trade_date
                     ),
             w20 AS (
                     PARTITION BY ticker_code
                     ORDER BY trade_date
                     ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
                     ),
             w30 AS (
                     PARTITION BY ticker_code
                     ORDER BY trade_date
                     ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
                     )
     ),
     inserted AS (
INSERT INTO public.t_stock_price_data (
    stock_id,
    collect_id,
    source_type,
    trade_date,
    ticker_name,
    ticker_code,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    daily_change,
    ma_20,
    volatility,
    dd_high,
    ret_low
)
SELECT
    stock_id,
    collect_id,
    source_type,
    trade_date,
    ticker_name,
    ticker_code,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    daily_change,
    CASE WHEN cnt_20 >= 20 THEN ma_20_calc END,
    CASE WHEN cnt_20 >= 20 THEN volatility_calc END,
    CASE WHEN cnt_30 >= 30 THEN dd_high_calc END,
    CASE WHEN cnt_30 >= 30 THEN ret_low_calc END
FROM calculated
WHERE stock_id IN (
    SELECT stock_id
    FROM target_rows
)
    RETURNING stock_id
)
UPDATE public.t_stock_original_price_data
SET
    calculated_yn = true,
    updated_dt = CURRENT_TIMESTAMP
WHERE stock_id IN (
    SELECT stock_id
    FROM inserted
);