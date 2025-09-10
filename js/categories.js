// categories.js - система управления категориями товаров
const categorySystem = {
    currentCategory: 'all',
    showVatPrices: false,
    
    init: function() {
        console.log('Инициализация системы категорий...');
        this.setupEventListeners();
    },
    
    setupEventListeners: function() {
        // Обработчики для переключения категорий
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const category = e.currentTarget.dataset.category;
                this.selectCategory(category);
            });
        });
    },
    
    selectCategory: function(category) {
        console.log('Выбрана категория:', category);
        this.currentCategory = category;
        
        // Обновляем активную кнопку
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-category="${category}"]`).classList.add('active');
        
        // Показываем/скрываем фильтры
        this.showCategoryFilters(category);
        
        // Фильтруем товары
        if (typeof filterProducts === 'function') {
            filterProducts();
        }
    },
    
    showCategoryFilters: function(category) {
        // Скрываем все фильтры
        document.querySelectorAll('.category-filter-content').forEach(el => {
            el.style.display = 'none';
        });
        
        // Показываем фильтры для выбранной категории
        if (category !== 'all') {
            document.getElementById('category-filters').style.display = 'block';
            document.getElementById(`${category}-filters`).style.display = 'block';
        } else {
            document.getElementById('category-filters').style.display = 'none';
        }
    },
    
    toggleVatPrices: function() {
        this.showVatPrices = !this.showVatPrices;
        if (typeof renderProducts === 'function') {
            renderProducts();
        }
    },
    
    // Функция для фильтрации товаров по категории
    filterByCategory: function(products) {
        if (this.currentCategory === 'all') {
            return products;
        }
        return products.filter(product => product.Тип === this.currentCategory);
    },
    
    // Функция для отображения цен с учетом НДС
    formatPrice: function(price) {
        if (this.showVatPrices) {
            // Показываем обе цены (с НДС и без)
            const priceWithVat = price * 1.2; // НДС 20%
            return `
                <div class="price-with-vat">${Math.round(priceWithVat).toLocaleString()} руб. с НДС</div>
                <div class="price-without-vat">${Math.round(price).toLocaleString()} руб. без НДС</div>
            `;
        } else {
            // Показываем только цену с НДС
            return `<div class="price-with-vat">${Math.round(price * 1.2).toLocaleString()} руб.</div>`;
        }
    }
};

// Делаем систему категорий доступной глобально
window.categorySystem = categorySystem;