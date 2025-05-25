// Archivo: frontend/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    // --- Referencias a elementos del DOM ---
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

    // --- Referencias a elementos del Modal ---
    const modal = document.getElementById('myModal');
    const modalTitle = document.getElementById('modal-title');
    const modalBody = document.getElementById('modal-body');
    const closeButton = document.querySelector('.close-button');
    const modalOkButton = document.getElementById('modal-ok-button');


    // --- Variables de estado ---
    let selectedProductInfo = null; // Objeto que almacenará info del producto/sucursal seleccionado para la venta
    let currentExchangeRate = 0; // Guardará el tipo de cambio USD/CLP

    // --- Formateador de moneda para CLP (Pesos Chilenos) ---
    // Configurado para estilo de moneda, con el símbolo CLP y sin decimales (común en Chile)
    const clpFormatter = new Intl.NumberFormat('es-CL', {
        style: 'currency',
        currency: 'CLP',
        minimumFractionDigits: 0, // Mínimo de decimales (0 para CLP)
        maximumFractionDigits: 0  // Máximo de decimales (0 para CLP)
    });

    // --- Formateador de moneda para USD (Dólares Estadounidenses) ---
    // Configurado para estilo de moneda, con el símbolo USD y 2 decimales
    const usdFormatter = new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });


    // --- Funciones de Interacción con el Backend API ---

    // Función para buscar productos
    async function searchProducts(query) {
        // Limpiar resultados anteriores y mensajes
        productResultsList.innerHTML = '';
        selectedProductInfo = null; // Limpiar selección previa
        resetSaleDetails(); // Limpiar sección de detalle de venta
        displayMessage('', '', statusMessagePara); // Limpiar mensajes de estado
        displayMessage('Buscando...', 'info', searchMessagePara);


        // Realizar llamada GET a tu API de backend (/api/productos/buscar?q=...)
        await fetch(`/api/productos/buscar?q=${encodeURIComponent(query)}`)
        .then(response => {
             if (!response.ok) {
                 // Manejar respuestas de error HTTP (ej: 400, 404, 500)
                 // Si es 404, el backend ya envía un mensaje "No products found"
                 return response.json().then(err => {
                     const errorMessage = err.message || `HTTP error! status: ${response.status}`;
                     throw new Error(errorMessage);
                 });
             }
             return response.json();
        })
        .then(data => {
            // data debería ser un array de productos, cada uno con sucursales_info
            // [
            //   {
            //     "id": 1, "nombre": "Martillo", "marca": "ToolCo",
            //     "sucursales_info": [
            //       {"sucursal_id": 1, "nombre": "Sucursal Centro", "precio": 10.50, "stock": 50}, ...
            //     ]
            //   }, ...
            // ]
            displaySearchResults(data);
        })
        .catch(error => {
            console.error('Error buscando productos:', error);
            // Mostrar el mensaje de error del backend o un mensaje genérico
            displayMessage(`Error al buscar productos: ${error.message}`, 'error', searchMessagePara);
        });
    }

    // Función para mostrar los resultados de la búsqueda en el HTML
    function displaySearchResults(products) {
        productResultsList.innerHTML = ''; // Limpiar resultados anteriores

        if (products && products.length > 0) {
            products.forEach(product => {
                 const productItem = document.createElement('li');
                 productItem.classList.add('product-result-item');

                 // Encabezado del producto
                 const productHeader = document.createElement('h4');
                 productHeader.textContent = `${product.nombre} (${product.marca || 'N/A'}) - ID: ${product.id}`;
                 productItem.appendChild(productHeader);

                 const branchListForProduct = document.createElement('ul');

                if (product.sucursales_info && product.sucursales_info.length > 0) {
                    product.sucursales_info.forEach(branch => {
                        const li = document.createElement('li');
                        li.classList.add('branch-info-item');
                        // Almacenar toda la info relevante en los data attributes
                        li.dataset.productId = product.id;
                        li.dataset.productName = product.nombre; // Guardar nombre del producto
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

         // Rellenar la sección de detalle de venta
         selectedProductNameSpan.textContent = selectedProductInfo.productName;
         selectedBranchNameSpan.textContent = selectedProductInfo.branchName;
         selectedProductStockSpan.textContent = selectedProductInfo.stock;
         unitPriceClpSpan.textContent = clpFormatter.format(selectedProductInfo.price); // Mostrar precio unitario formateado
         quantityInput.value = 1; // Resetear cantidad a 1
         calculateTotals(); // Recalcular totales al seleccionar
         displayMessage(`Producto seleccionado en ${selectedProductInfo.branchName}. Stock disponible: ${selectedProductInfo.stock}`, 'info', statusMessagePara);

         // Validar cantidad inicial (que es 1) y habilitar/deshabilitar botón de venta
         validateQuantity();
    }

     // Función para resetear la sección de detalle de venta
     function resetSaleDetails() {
         selectedProductInfo = null;
         selectedProductNameSpan.textContent = 'Ninguno';
         selectedBranchNameSpan.textContent = 'Ninguna';
         selectedProductStockSpan.textContent = 'N/A';
         unitPriceClpSpan.textContent = clpFormatter.format(0); // Formatear 0 CLP
         quantityInput.value = 1;
         totalClpSpan.textContent = clpFormatter.format(0); // Formatear 0 CLP
         totalUsdSpan.textContent = usdFormatter.format(0); // Formatear 0 USD
         sellButton.disabled = true; // Deshabilitar botón de venta
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
            // La validación de cantidad ya muestra un mensaje si es inválida
            return;
        }

        const totalClp = quantity * price;
        totalClpSpan.textContent = clpFormatter.format(totalClp); // Formato de moneda para CLP

        // Calcular total en USD si tenemos el tipo de cambio
        if (currentExchangeRate > 0) {
            console.log('DEBUG (Frontend): totalClp para USD:', totalClp);
            console.log('DEBUG (Frontend): currentExchangeRate para USD:', currentExchangeRate);
            const totalUsd = totalClp / currentExchangeRate;
            console.log('DEBUG (Frontend): calculated totalUsd:', totalUsd);
            totalUsdSpan.textContent = usdFormatter.format(totalUsd); // Formato de moneda para USD
        } else {
            totalUsdSpan.textContent = 'N/A'; // Mostrar N/A si el tipo de cambio no está disponible
        }
    }

     // Función para validar la cantidad ingresada
     function validateQuantity() {
         const quantity = parseInt(quantityInput.value, 10);
         const stock = selectedProductInfo ? selectedProductInfo.stock : 0;

         if (isNaN(quantity) || quantity <= 0) {
             displayMessage('La cantidad debe ser un número positivo (mínimo 1).', 'warning', statusMessagePara);
             // quantityInput.value = 1; // No resetear automáticamente para que el usuario vea su entrada inválida
             sellButton.disabled = true; // Deshabilitar botón de venta
             return false;
         }

         if (selectedProductInfo && quantity > stock) {
             displayMessage(`Cantidad solicitada (${quantity}) supera el stock disponible (${stock}) en esta sucursal.`, 'warning', statusMessagePara);
             sellButton.disabled = true; // Deshabilitar botón de venta
             return false;
         } else {
             // Si la cantidad es válida y hay stock suficiente
             displayMessage('', '', statusMessagePara); // Limpiar mensaje de validación
             if (selectedProductInfo) { // Solo habilitar si hay un producto seleccionado
                sellButton.disabled = false; // Habilitar botón de venta
             }
             return true;
         }
     }


    // Función para realizar la venta
    async function performSale() {
        if (!selectedProductInfo) {
             showModal('Error', 'Por favor, selecciona un producto y sucursal primero.');
            return;
        }

        if (!validateQuantity()) {
             return;
        }

        const quantity = parseInt(quantityInput.value, 10);
        const totalClpToPay = selectedProductInfo.price * quantity; // Asegúrate de que este es el monto total

        // Datos que enviarás al backend para iniciar la transacción de venta/pago
        const saleData = {
            product_id: selectedProductInfo.productId,
            branch_id: selectedProductInfo.branchId,
            quantity: quantity,
            total_amount: totalClpToPay // Agrega el monto total para que el backend lo use con Transbank
        };

        displayMessage('Iniciando proceso de pago...', 'info', statusMessagePara);
        sellButton.disabled = true; // Deshabilitar botón durante el proceso

        await fetch('/api/venta', { // La ruta de venta ahora también maneja Transbank
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(saleData),
        })
        .then(response => {
             // sellButton.disabled = false; // No habilitar aquí, se habilitará después de la redirección o error
             if (!response.ok) {
                 return response.json().then(err => {
                     const errorMessage = err.message || `HTTP error! status: ${response.status}`;
                     throw new Error(errorMessage);
                 });
             }
             return response.json();
        })
        .then(data => {
            if (data.token && data.url) {
                // Si el backend devuelve un token y una URL de Transbank, redirigir al usuario
                displayMessage('Redirigiendo a Transbank...', 'info', statusMessagePara);
                window.location.href = data.url; // ¡Redirigir al cliente a la página de pago de Transbank!
            } else if (data.message) {
                // Si hay un mensaje, pero no token/url (ej. error de stock desde el backend)
                showModal('Mensaje', data.message);
                displayMessage(data.message, 'warning', statusMessagePara);
                sellButton.disabled = false; // Habilitar botón si no hay redirección
            } else {
                showModal('Error', 'Respuesta inesperada del servidor.');
                displayMessage('Error: Respuesta inesperada del servidor.', 'error', statusMessagePara);
                sellButton.disabled = false; // Habilitar botón si no hay redirección
            }
        })
        .catch(error => {
            sellButton.disabled = false; // Asegurarse de habilitar el botón en caso de error
            console.error('Error en la venta o inicio de pago:', error);
            showModal('Error de Comunicación', `Error de comunicación con el servidor: ${error.message}. Intenta de nuevo.`);
            displayMessage('Error de comunicación con el servidor.', 'error', statusMessagePara);
        });

        displayMessage('Procesando venta...', 'info', statusMessagePara);
        sellButton.disabled = true; // Deshabilitar botón durante el proceso

        await fetch('/api/venta', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(saleData),
        })
        .then(response => {
            sellButton.disabled = false; // Habilitar botón de nuevo
             if (!response.ok) {
                 // Manejar respuestas de error HTTP (ej: 400, 404, 500)
                 return response.json().then(err => {
                     const errorMessage = err.message || `HTTP error! status: ${response.status}`;
                     throw new Error(errorMessage);
                 });
             }
             return response.json(); // Asumimos que el backend devuelve JSON
        })
        .then(data => {
            // Manejar la respuesta del backend (éxito, error, nuevo stock)
            if (data.message && data.message.includes('successfully')) { // TODO: Usar un flag 'success' en la respuesta del backend
                showModal('Venta Exitosa', `Venta realizada con éxito. Nuevo stock para ${data.product_name} en ${data.branch_name}: ${data.new_stock}`);
                displayMessage('Venta realizada con éxito.', 'success', statusMessagePara);
                // Opcional: Actualizar el stock mostrado en la sección de detalle de venta
                selectedProductInfo.stock = data.new_stock;
                selectedProductStockSpan.textContent = selectedProductInfo.stock;
                 // Opcional: Volver a buscar el producto para actualizar la lista de resultados visualmente
                 // searchProducts(productSearchInput.value.trim());
            } else {
                 // Si el backend devuelve un mensaje de error específico (ej: stock insuficiente)
                 showModal('Error en la Venta', data.message || 'Ocurrió un error al procesar la venta.');
                 displayMessage(`Error al realizar la venta: ${data.message || 'Error desconocido'}`, 'error', statusMessagePara);
                 // Si el error es por stock insuficiente, actualizar el stock mostrado si el backend lo devuelve
                 if (data.available_stock !== undefined) {
                      selectedProductInfo.stock = data.available_stock;
                      selectedProductStockSpan.textContent = selectedProductInfo.stock;
                 }
            }
        })
        .catch(error => {
            sellButton.disabled = false; // Asegurarse de habilitar el botón en caso de error
            console.error('Error en la venta:', error);
            showModal('Error de Comunicación', `Error de comunicación con el servidor: ${error.message}. Intenta de nuevo.`);
            displayMessage('Error de comunicación con el servidor.', 'error', statusMessagePara);
        });
    }

    // Función para obtener el tipo de cambio USD/CLP
    async function getExchangeRate() {
        // Llamar al endpoint del backend que a su vez llama a la API externa (/api/exchange_rate)
        await fetch('/api/exchange_rate')
        .then(response => {
             if (!response.ok) {
                  console.warn(`HTTP error getting exchange rate! status: ${response.status}`);
                  // No lanzar error aquí, solo advertir y dejar currentExchangeRate en 0
                  return response.json().catch(() => ({})); // Intentar parsear JSON, si falla, devolver objeto vacío
             }
             return response.json();
        })
        .then(data => {
            if (data && data.rate) {
                currentExchangeRate = data.rate;
                console.log('DEBUG (Frontend): Tipo de cambio obtenido del backend:', currentExchangeRate);
                // Recalcular totales si ya hay un producto seleccionado
                calculateTotals();
            } else {
                console.warn('DEBUG (Frontend): No se pudo obtener un tipo de cambio válido del backend.');
                currentExchangeRate = 0; // Asegurarse de que sea 0 en caso de respuesta inválida
                totalUsdSpan.textContent = 'N/A'; // Mostrar N/A si no hay tipo de cambio
            }
        })
        .catch(error => {
            console.error('DEBUG (Frontend): Error obteniendo tipo de cambio del backend:', error);
            currentExchangeRate = 0; // Asegurarse de que sea 0 en caso de error
            totalUsdSpan.textContent = 'N/A'; // Mostrar N/A si hay error
        });
    }

    // --- Implementación de Server-Sent Events (SSE) para Stock Bajo ---
    function setupLowStockSSE() {
         // Verificar si el navegador soporta SSE
         if (typeof EventSource !== "undefined") {
             // Configurar la conexión SSE a tu endpoint de backend (/events/low-stock)
             const eventSource = new EventSource('/events/low-stock');

             eventSource.onmessage = function(event) {
                 // Este handler se llama para mensajes sin un 'event:' especificado
                 // No esperamos mensajes sin evento para stock bajo, pero es buena práctica tenerlo
                 console.log("Received generic SSE message:", event.data);
             };

             eventSource.addEventListener('low_stock_alert', function(event) {
                 // Este handler se llama específicamente para eventos con 'event: low_stock_alert'
                 try {
                     const notificationData = JSON.parse(event.data);
                     // notificationData debería contener { product_name: '...', branch_name: '...', current_stock: ... }
                     console.log("Received low stock alert:", notificationData);

                     const notificationElement = document.createElement('p');
                     notificationElement.textContent = `¡Alerta de Stock Bajo! Producto "${notificationData.product_name}" en "${notificationData.branch_name}". Stock actual: ${notificationData.current_stock}`;
                     notificationElement.className = 'low-stock-alert message error'; // Estilo para alertas
                     // Añadir la notificación al inicio de la lista para que las más recientes aparezcan primero
                     lowStockNotificationsDiv.insertBefore(notificationElement, lowStockNotificationsDiv.firstChild);

                     // Opcional: Limitar el número de notificaciones mostradas
                     while (lowStockNotificationsDiv.children.length > 10) { // Mantener solo las últimas 10 (más el h3)
                         lowStockNotificationsDiv.removeChild(lowStockNotificationsDiv.lastChild);
                     }

                 } catch (e) {
                     console.error("Error parsing SSE message data:", e);
                     console.log("Received raw SSE data:", event.data);
                 }
             });


             eventSource.onerror = function(error) {
                 console.error('Error en la conexión SSE:', error);
                 // Opcional: Intentar reconectar o mostrar un mensaje de error al usuario
                 // eventSource.close(); // Cerrar la conexión actual en caso de error
                 // setTimeout(setupLowStockSSE, 5000); // Intentar reconectar después de 5 segundos
                 // Mostrar un mensaje de error en la interfaz si la conexión falla
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

    // Función para mostrar mensajes en un elemento específico
    function displayMessage(message, type = 'info', element) {
        if (element) {
            element.textContent = message;
            element.className = `message ${type}`; // Añade clases para estilizar
        } else {
             console.log(`Message (${type}): ${message}`); // Fallback a consola si no hay elemento
        }
    }

    // Función para mostrar la ventana emergente (Modal)
    function showModal(title, body) {
        modalTitle.textContent = title;
        modalBody.textContent = body;
        modal.style.display = 'block';
    }

     // Función para ocultar la ventana emergente (Modal)
    function hideModal() {
        modal.style.display = 'none';
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
            event.preventDefault(); // Evitar el envío de formulario por defecto
            searchButton.click(); // Simular clic en el botón de búsqueda
        }
    });

    // Evento para los botones "Seleccionar" (delegación de eventos en la lista de resultados)
    // Usamos delegation en la lista de productos para capturar clics en botones "Seleccionar"
    productResultsList.addEventListener('click', (event) => {
        if (event.target.classList.contains('select-product-btn')) {
            // El botón está dentro de un li.branch-info-item, que tiene los data attributes
            const branchInfoItem = event.target.closest('.branch-info-item');
            if (branchInfoItem) {
                selectProduct(branchInfoItem); // Pasar el elemento li con los data attributes
            }
        }
    });

    // Evento para recalcular totales y validar cantidad al cambiar la cantidad
    quantityInput.addEventListener('input', () => {
        validateQuantity(); // Validar cantidad cada vez que cambia
        calculateTotals();
    });

    // Evento para el botón de calcular USD (aunque el cálculo se hace en input change)
    calculateButton.addEventListener('click', calculateTotals);


    // Evento para el botón de venta
    sellButton.addEventListener('click', performSale);

    // Eventos para cerrar el Modal
    closeButton.addEventListener('click', hideModal);
    modalOkButton.addEventListener('click', hideModal);
    // Cerrar modal si se hace clic fuera del contenido
    window.addEventListener('click', (event) => {
        if (event.target === modal) {
            hideModal();
        }
    });


    // --- Inicialización ---
    // Al cargar la página, intenta obtener el tipo de cambio
    getExchangeRate();
    // Configurar la conexión SSE para notificaciones de stock bajo
    setupLowStockSSE();
    // La vista de venta ya está activa por defecto en el HTML simplificado.
});
