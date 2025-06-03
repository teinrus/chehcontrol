// Проверяем, что скрипт загрузился
console.log('Report filter JS loaded');

document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded');

    const lineSelect = document.getElementById('id_line');
    const shiftSelect = document.getElementById('id_shift');

    // Проверяем, что элементы найдены
    if (!lineSelect) {
        console.error('Line select element not found!');
        return;
    }
    if (!shiftSelect) {
        console.error('Shift select element not found!');
        return;
    }

    console.log('Found elements:', { lineSelect, shiftSelect });

    function updateShifts() {
        const lineId = lineSelect.value;
        console.log('Selected line ID:', lineId);

        if (!lineId) {
            console.log('No line selected, resetting shifts');
            shiftSelect.innerHTML = '<option value="">Все сутки</option>';
            return;
        }

        // Очищаем текущий список смен
        shiftSelect.innerHTML = '<option value="">Все сутки</option>';

        // Загружаем смены для выбранной линии
        const url = `/downtimes/get_shifts/?line=${lineId}`;
        console.log('Fetching shifts from URL:', url);

        fetch(url)
            .then(response => {
                console.log('Response status:', response.status);
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Received shifts data:', data);
                if (Array.isArray(data)) {
                    data.forEach(shift => {
                        const option = document.createElement('option');
                        option.value = shift.id;
                        option.textContent = shift.name;
                        shiftSelect.appendChild(option);
                    });
                } else {
                    console.error('Received data is not an array:', data);
                }
            })
            .catch(error => {
                console.error('Error fetching shifts:', error);
                shiftSelect.innerHTML = '<option value="">Ошибка загрузки смен</option>';
            });
    }

    // Обновляем список смен только при изменении значения в выпадающем списке
    lineSelect.addEventListener('change', function (e) {
        console.log('Line selection changed:', e.target.value);
        updateShifts();
    });

    // Удаляем обработчик клика, если он был
    lineSelect.removeEventListener('click', updateShifts);

    // Обновляем список смен при первой загрузке страницы только если есть выбранное значение
    if (lineSelect.value) {
        console.log('Initial line value:', lineSelect.value);
        updateShifts();
    }
}); 