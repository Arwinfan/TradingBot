/**
 * 币安量化交易系统 - 前端脚本
 * 包含公共函数和工具
 */

// 全局命名空间
const TradingSystem = {
    // API请求
    async api(endpoint, options = {}) {
        try {
            const response = await fetch(endpoint, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers,
                },
                ...options,
            });
            return await response.json();
        } catch (error) {
            console.error('API请求失败:', error);
            throw error;
        }
    },

    // 格式化价格
    formatPrice(price, decimals = 2) {
        if (price === null || price === undefined) return '-';
        if (price >= 1000) return price.toLocaleString('zh-CN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
        if (price >= 1) return price.toFixed(decimals);
        if (price >= 0.01) return price.toFixed(4);
        return price.toFixed(6);
    },

    // 格式化数量
    formatAmount(amount, decimals = 4) {
        if (amount === null || amount === undefined) return '-';
        return amount.toFixed(decimals);
    },

    // 格式化成交量
    formatVolume(volume) {
        if (volume === null || volume === undefined) return '-';
        if (volume >= 1000000000) return (volume / 1000000000).toFixed(2) + 'B';
        if (volume >= 1000000) return (volume / 1000000).toFixed(2) + 'M';
        if (volume >= 1000) return (volume / 1000).toFixed(2) + 'K';
        return volume.toFixed(2);
    },

    // 格式化百分比
    formatPercent(percent, showSign = true) {
        if (percent === null || percent === undefined) return '-';
        const sign = showSign && percent > 0 ? '+' : '';
        return sign + percent.toFixed(2) + '%';
    },

    // 格式化时间
    formatTime(timestamp) {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        return date.toLocaleString('zh-CN');
    },

    // 显示通知
    notify(message, type = 'info') {
        // 简单的alert实现，可替换为更复杂的通知组件
        const colors = {
            success: '#238636',
            error: '#da3633',
            warning: '#d29922',
            info: '#58a6ff'
        };
        console.log(`[${type.toUpperCase()}] ${message}`);
    },

    // 防抖
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // 节流
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// 导出到全局
window.TradingSystem = TradingSystem;
