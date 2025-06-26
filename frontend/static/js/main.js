// Archivo: frontend/static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Referencias a elementos del DOM existentes ---
    const productSearchInput = document.getElementById('product-search');
    const searchButton = document.getElementById('search-button');
    const productResultsList = document.getElementById('product-results-list'); // Lista para mostrar productos encontrados
    const searchMessagePara = document.getElementById('search-message');

    const selectedProductNameSpan = document.getElementById('selected-product-name');
    const selectedBranchNameSpan = document.getElementById('selected-branch-name');
    const selectedProductStockSpan = document.getElementById('selected-product-stock'); // Para mostrar el stock disponible
    const quantityInput = document.getElementById('quantity');
    const calculateButton = document.getElementById('calculate-button');
    const unitPriceClpSpan = document.getElementById('unit-price-clp'); // Para mostrar el precio unitario
    const totalClpSpan = document.getElementById('total-clp');
    const totalUsdSpan = document.getElementById('total-usd');
    const sellButton = document.getElementById('sell-button');
    const statusMessagePara = document.getElementById('status-message');
    const lowStockNotificationsDiv = document.getElementById('low-stock-notifications');

    // --- Referencias a elementos del Modal de Confirmación existente (#myModal) ---
    const modal = document.getElementById('myModal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    // Usamos un selector más específico para el botón de cerrar del modal de confirmación
    const closeButton = document.querySelector('#myModal .close-button'); 
    const modalOkButton = document.getElementById('modal-ok-button');

    // --- NUEVAS Referencias a elementos del DOM para el modal de formulario de producto (#productFormModal) ---
    const addProductButton = document.getElementById('add-product-button');
    const productFormModal = document.getElementById('productFormModal');
    const closeProductFormModalButton = document.getElementById('close-product-form-modal'); // Botón 'x' del nuevo modal
    const cancelProductButton = document.getElementById('cancel-product-button'); // Botón 'Cancelar' del formulario
    const productForm = document.getElementById('product-form');
    const productNameInput = document.getElementById('product-name');
    const productDescriptionInput = document.getElementById('product-description');
    const productPriceInput = document.getElementById('product-price');
    const productImageInput = document.getElementById('product-image');
    const imagePreview = document.getElementById('image-preview');
    const saveProductButton = document.getElementById('save-product-button');

    let base64Image = null; // Variable para almacenar la imagen en Base64

    // --- Variables de estado ---
    let selectedProductInfo = null; // Objeto que almacenará info del producto/sucursal seleccionado para la venta
    let currentExchangeRate = 0; // Guardará el tipo de cambio USD/CLP

    // --- Formateadores de moneda ---
    const clpFormatter = new Intl.NumberFormat('es-CL', {
        style: 'currency',
        currency: 'CLP',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
    const usdFormatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });


    // --- Funciones de Interacción con el Backend API ---

    // Función para buscar productos
    async function searchProducts(query) {
        productResultsList.innerHTML = '';
        selectedProductInfo = null;
        resetSaleDetails();
        displayMessage('', '', statusMessagePara);
        displayMessage('Buscando...', 'info', searchMessagePara);

        try {
            const response = await fetch(`/api/productos/buscar?q=${encodeURIComponent(query)}`);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            displaySearchResults(data);
        } catch (error) {
            console.error('Error buscando productos:', error);
            displayMessage(`Error al buscar productos: ${error.message}`, 'error', searchMessagePara);
        }
    }

    // Función para mostrar los resultados de la búsqueda en el HTML
    function displaySearchResults(products) {
        productResultsList.innerHTML = '';

        if (products && products.length > 0) {
            products.forEach(product => {
                const productItem = document.createElement('li');
                productItem.classList.add('product-result-item');

                const productHeader = document.createElement('h4');
                productHeader.textContent = `${product.nombre} (${product.marca || 'N/A'}) - ID: ${product.id}`;
                productItem.appendChild(productHeader);

                // Si el producto tiene imagen en base64, mostrarla
                if (product.imagen_base64) {
                    const img = document.createElement('img');
                    img.src = `data:image/jpeg;base64,${product.imagen_base64}`; 
                    img.alt = `Imagen de ${product.nombre}`;
                    img.style.maxWidth = '100px';
                    img.style.maxHeight = '100px';
                    img.style.borderRadius = '4px';
                    img.style.marginBottom = '10px';
                    img.style.border = '1px solid #ddd';
                    productItem.appendChild(img);
                }


                const branchListForProduct = document.createElement('ul');

                if (product.sucursales_info && product.sucursales_info.length > 0) {
                    product.sucursales_info.forEach(branch => {
                        const li = document.createElement('li');
                        li.classList.add('branch-info-item');
                        li.dataset.productId = product.id;
                        li.dataset.productName = product.nombre;
                        li.dataset.branchId = branch.sucursal_id;
                        li.dataset.price = branch.precio;
                        li.dataset.stock = branch.stock;
                        li.dataset.branchName = branch.nombre;

                        li.innerHTML = `
                            ${branch.nombre}: Cant: <span class="branch-stock">${branch.stock}</span> | Precio: <span class="branch-price">${clpFormatter.format(branch.precio)}</span>
                            <button class="select-product-btn">Seleccionar</button>
                        `;
                        branchListForProduct.appendChild(li);
                    });
                } else {
                    const li = document.createElement('li');
                    li.textContent = `No se encontró stock para este producto en ninguna sucursal.`;
                    branchListForProduct.appendChild(li);
                }
                productItem.appendChild(branchListForProduct);
                productResultsList.appendChild(productItem);
            });
            displayMessage(`Resultados encontrados para "${productSearchInput.value}"`, 'success', searchMessagePara);

        } else {
            displayMessage('No se encontraron resultados.', 'info', searchMessagePara);
        }
    }

    // Función para manejar la selección de un producto/sucursal
    function selectProduct(button) {
        selectedProductInfo = {
            productId: parseInt(button.dataset.productId, 10),
            productName: button.dataset.productName,
            branchId: parseInt(button.dataset.branchId, 10),
            branchName: button.dataset.branchName,
            price: parseFloat(button.dataset.price),
            stock: parseInt(button.dataset.stock, 10)
        };

        selectedProductNameSpan.textContent = selectedProductInfo.productName;
        selectedBranchNameSpan.textContent = selectedProductInfo.branchName;
        selectedProductStockSpan.textContent = selectedProductInfo.stock;
        unitPriceClpSpan.textContent = clpFormatter.format(selectedProductInfo.price);
        quantityInput.value = 1;
        calculateTotals();
        displayMessage(`Producto seleccionado en ${selectedProductInfo.branchName}. Stock disponible: ${selectedProductInfo.stock}`, 'info', statusMessagePara);
        validateQuantity();
    }

    // Función para resetear la sección de detalle de venta
    function resetSaleDetails() {
        selectedProductInfo = null;
        selectedProductNameSpan.textContent = 'Ninguno';
        selectedBranchNameSpan.textContent = 'Ninguna';
        selectedProductStockSpan.textContent = 'N/A';
        unitPriceClpSpan.textContent = clpFormatter.format(0);
        quantityInput.value = 1;
        totalClpSpan.textContent = clpFormatter.format(0);
        totalUsdSpan.textContent = usdFormatter.format(0);
        sellButton.disabled = true;
    }

    // Función para calcular el total en CLP y USD
    function calculateTotals() {
        if (!selectedProductInfo) {
            totalClpSpan.textContent = clpFormatter.format(0);
            totalUsdSpan.textContent = usdFormatter.format(0);
            return;
        }

        const quantity = parseInt(quantityInput.value, 10);
        const price = selectedProductInfo.price;

        if (isNaN(quantity) || quantity <= 0) {
            totalClpSpan.textContent = clpFormatter.format(0);
            totalUsdSpan.textContent = usdFormatter.format(0);
            return;
        }

        const totalClp = quantity * price;
        totalClpSpan.textContent = clpFormatter.format(totalClp);

        if (currentExchangeRate > 0) {
            const totalUsd = totalClp / currentExchangeRate;
            totalUsdSpan.textContent = usdFormatter.format(totalUsd);
        } else {
            totalUsdSpan.textContent = 'N/A';
        }
    }

    // Función para validar la cantidad ingresada
    function validateQuantity() {
        const quantity = parseInt(quantityInput.value, 10);
        const stock = selectedProductInfo ? selectedProductInfo.stock : 0;

        if (isNaN(quantity) || quantity <= 0) {
            displayMessage('La cantidad debe ser un número positivo (mínimo 1).', 'warning', statusMessagePara);
            sellButton.disabled = true;
            return false;
        }

        if (selectedProductInfo && quantity > stock) {
            displayMessage(`Cantidad solicitada (${quantity}) supera el stock disponible (${stock}) en esta sucursal.`, 'warning', statusMessagePara);
            sellButton.disabled = true;
            return false;
        } else {
            displayMessage('', '', statusMessagePara);
            if (selectedProductInfo) {
                sellButton.disabled = false;
            }
            return true;
        }
    }

    // --- Función para generar un UUID simple ---
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // Función para realizar la venta (AHORA LLAMA A TRANSBANK)
    async function performSale() {
        if (!selectedProductInfo) {
            showModal('Error', 'Por favor, selecciona un producto y sucursal primero.');
            return;
        }

        if (!validateQuantity()) {
            return;
        }

        const quantity = parseInt(quantityInput.value, 10);
        const totalClpToPay = selectedProductInfo.price * quantity;

        // Generar un buy_order y session_id únicos
        const buyOrder = `order-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
        const sessionId = generateUUID(); // Usar un UUID para la sesión

        // Construir cart_items
        const cartItems = [{
            product_id: selectedProductInfo.productId,
            sucursal_id: selectedProductInfo.branchId,
            quantity: quantity,
            price: selectedProductInfo.price
        }];

        // Datos que enviarás al backend para iniciar la transacción de Transbank
        const transbankData = {
            buy_order: buyOrder,
            session_id: sessionId,
            amount: totalClpToPay,
            cart_items: cartItems
        };

        displayMessage('Iniciando proceso de pago con Transbank...', 'info', statusMessagePara);
        sellButton.disabled = true;

        try {
            const response = await fetch('/api/webpay/create', { // <<-- ¡NUEVA RUTA!
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(transbankData),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || errorData.message || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.url && data.token) {
                console.log('DEBUG (Frontend): Redireccionando a URL de Transbank:', data.url); // LOG DEPURACIÓN
                displayMessage('Redirigiendo a Transbank...', 'info', statusMessagePara);
                // Redirigir al usuario a la URL de Transbank
                window.location.href = data.url;
            } else if (data.message || data.error) {
                console.log('DEBUG (Frontend): Respuesta de Transbank CREATE no exitosa:', data.message || data.error); // LOG DEPURACIÓN
                showModal('Mensaje', data.message || data.error);
                displayMessage(data.message || data.error, 'warning', statusMessagePara);
                sellButton.disabled = false;
            } else {
                console.log('DEBUG (Frontend): Respuesta inesperada de Transbank CREATE:', data); // LOG DEPURACIÓN
                showModal('Error', 'Respuesta inesperada del servidor al iniciar Transbank.');
                displayMessage('Error: Respuesta inesperada del servidor.', 'error', statusMessagePara);
                sellButton.disabled = false;
            }

        } catch (error) {
            sellButton.disabled = false;
            console.error('ERROR (Frontend): Fallo en el inicio de pago con Transbank:', error); // LOG DEPURACIÓN
            showModal('Error de Comunicación', `Error de comunicación con el servidor al iniciar Transbank: ${error.message}. Intenta de nuevo.`);
            displayMessage('Error de comunicación con el servidor.', 'error', statusMessagePara);
        }
    }

    // Función para obtener el tipo de cambio USD/CLP
    async function getExchangeRate() {
        try {
            const response = await fetch('/api/exchange_rate');
            if (!response.ok) {
                console.warn(`HTTP error getting exchange rate! status: ${response.status}`);
                return response.json().catch(() => ({}));
            }
            const data = await response.json();
            if (data && data.rate) {
                currentExchangeRate = data.rate;
                console.log('DEBUG (Frontend): Tipo de cambio obtenido del backend:', currentExchangeRate);
                calculateTotals();
            } else {
                console.warn('DEBUG (Frontend): No se pudo obtener un tipo de cambio válido del backend.');
                currentExchangeRate = 0;
                totalUsdSpan.textContent = 'N/A';
            }
        } catch (error) {
            console.error('DEBUG (Frontend): Error obteniendo tipo de cambio del backend:', error);
            currentExchangeRate = 0;
            totalUsdSpan.textContent = 'N/A';
        }
    }

    // --- Implementación de Server-Sent Events (SSE) para Stock Bajo ---
    function setupLowStockSSE() {
        if (typeof EventSource !== "undefined") {
            const eventSource = new EventSource('/events/low-stock');

            eventSource.onmessage = function(event) {
                console.log("Received generic SSE message:", event.data);
            };

            eventSource.addEventListener('low_stock_alert', function(event) {
                try {
                    const notificationData = JSON.parse(event.data);
                    console.log("Received low stock alert:", notificationData);

                    const notificationElement = document.createElement('p');
                    notificationElement.textContent = `¡Alerta de Stock Bajo! Producto "${notificationData.product_name}" en "${notificationData.branch_name}". Stock actual: ${notificationData.current_stock}`;
                    notificationElement.className = 'low-stock-alert message error';
                    lowStockNotificationsDiv.insertBefore(notificationElement, lowStockNotificationsDiv.firstChild);

                    while (lowStockNotificationsDiv.children.length > 10) {
                        lowStockNotificationsDiv.removeChild(lowStockNotificationsDiv.lastChild);
                    }

                } catch (e) {
                    console.error("Error parsing SSE message data:", e);
                    console.log("Received raw SSE data:", event.data);
                }
            });

            eventSource.onerror = function(error) {
                console.error('Error en la conexión SSE:', error);
                const errorElement = document.createElement('p');
                errorElement.textContent = `Error en la conexión de notificaciones de stock.`;
                errorElement.className = 'low-stock-alert message warning';
                lowStockNotificationsDiv.insertBefore(errorElement, lowStockNotificationsDiv.firstChild);
            };

            console.log("SSE setup complete. Listening for low_stock_alert events.");
        } else {
            console.warn("Server-Sent Events not supported by this browser.");
            const notificationElement = document.createElement('p');
            notificationElement.textContent = `Las notificaciones de stock bajo no son soportadas por tu navegador.`;
            notificationElement.className = 'low-stock-alert message warning';
            lowStockNotificationsDiv.appendChild(notificationElement);
        }
    }

    // --- Funciones de Utilidad ---
    function displayMessage(message, type = 'info', element) {
        if (element) {
            element.textContent = message;
            element.className = `message ${type}`;
        } else {
            console.log(`Message (${type}): ${message}`);
        }
    }

    function showModal(title, body) {
        modalTitle.textContent = title;
        modalBody.textContent = body;
        modal.style.display = 'flex'; // Usar 'flex' para centrar
    }

    function hideModal() {
        modal.style.display = 'none';
    }

    // --- NUEVAS Funciones para manejar el modal de producto ---

    // Función para abrir el modal de formulario de producto
    function openProductFormModal() {
        productForm.reset(); // Limpiar el formulario
        imagePreview.src = '#'; // Limpiar la vista previa de la imagen
        imagePreview.style.display = 'none'; // Ocultar la vista previa
        base64Image = null; // Reiniciar la variable de imagen
        productFormModal.style.display = 'flex'; // Mostrar el modal (usando flex para centrar)
        document.getElementById('product-form-title').textContent = 'Añadir Nuevo Producto'; // Asegurar el título
        saveProductButton.textContent = 'Guardar Producto'; // Asegurar el texto del botón
    }

    // Función para cerrar el modal de formulario de producto
    function closeProductFormModal() {
        productFormModal.style.display = 'none'; // Ocultar el modal
    }

    // --- Event Listeners ---

    // Evento para el botón de búsqueda
    searchButton.addEventListener('click', () => {
        const query = productSearchInput.value.trim();
        if (query) {
            searchProducts(query);
        } else {
            displayMessage('Por favor, ingresa un término de búsqueda.', 'warning', searchMessagePara);
        }
    });

    // Permitir búsqueda al presionar Enter en el campo de búsqueda
    productSearchInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            searchButton.click();
        }
    });

    // Evento para los botones "Seleccionar" (delegación de eventos en la lista de resultados)
    productResultsList.addEventListener('click', (event) => {
        if (event.target.classList.contains('select-product-btn')) {
            const branchInfoItem = event.target.closest('.branch-info-item');
            if (branchInfoItem) {
                selectProduct(branchInfoItem);
            }
        }
    });

    // Evento para recalcular totales y validar cantidad al cambiar la cantidad
    quantityInput.addEventListener('input', () => {
        validateQuantity();
        calculateTotals();
    });

    // Evento para el botón de calcular USD (aunque el cálculo se hace en input change)
    calculateButton.addEventListener('click', calculateTotals);


    // Evento para el botón de venta
    sellButton.addEventListener('click', performSale);

    // Eventos para cerrar el Modal general
    closeButton.addEventListener('click', hideModal);
    modalOkButton.addEventListener('click', hideModal);
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            hideModal();
        }
    });

    // --- NUEVOS Event Listeners para el modal de producto ---

    addProductButton.addEventListener('click', openProductFormModal);
    closeProductFormModalButton.addEventListener('click', closeProductFormModal);
    cancelProductButton.addEventListener('click', closeProductFormModal);

    // Ocultar modal si se hace clic fuera del contenido
    window.addEventListener('click', (event) => {
        if (event.target == productFormModal) {
            closeProductFormModal();
        }
    });

    // Manejar la vista previa de la imagen y conversión a Base64
    productImageInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            if (!file.type.startsWith('image/')) {
                showModal('Error de Archivo', 'Por favor, selecciona un archivo de imagen válido (JPEG, PNG, GIF, etc.).');
                productImageInput.value = '';
                imagePreview.style.display = 'none';
                base64Image = null;
                return;
            }

            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                imagePreview.style.display = 'block';
                base64Image = e.target.result.split(',')[1];
            };
            reader.readAsDataURL(file);
        } else {
            imagePreview.src = '#';
            imagePreview.style.display = 'none';
            base64Image = null;
        }
    });

    // --- Manejar el envío del formulario de producto ---
    productForm.addEventListener('submit', async (event) => {
        event.preventDefault();

        saveProductButton.disabled = true;

        const productName = productNameInput.value.trim();
        const productDescription = productDescriptionInput.value.trim();
        const productPrice = parseFloat(productPriceInput.value);

        if (!productName || isNaN(productPrice) || productPrice <= 0) {
            showModal('Error de Formulario', 'Por favor, completa el Nombre del Producto y un Precio Base válido (mayor que 0).');
            saveProductButton.disabled = false;
            return;
        }

        const productData = {
            name: productName,
            description: productDescription,
            price: productPrice,
            image: base64Image
        };

        try {
            const response = await fetch('/api/products/add', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(productData),
            });

            const result = await response.json();

            if (response.ok) {
                showModal('Producto Añadido', result.message);
                closeProductFormModal();
                productSearchInput.value = '';
                productResultsList.innerHTML = '';
                displayMessage('Producto añadido. Puedes buscarlo para verlo.', 'success', searchMessagePara);
            } else {
                showModal('Error al Añadir Producto', result.error || 'Ocurrió un error desconocido.');
            }
        } catch (error) {
            console.error('Error al enviar el producto:', error);
            showModal('Error de Comunicación', `Error de conexión o del servidor al guardar el producto: ${error.message}.`);
        } finally {
            saveProductButton.disabled = false;
        }
    });


    // --- Inicialización ---
    getExchangeRate();
    setupLowStockSSE();
    resetSaleDetails();
});
