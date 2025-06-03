document.addEventListener('DOMContentLoaded', function () {
    const lineSelect = document.getElementById('id_line');
    const shiftSelect = document.getElementById('id_shift');

    if (!lineSelect || !shiftSelect) {
        return;
    }

    // Сохраняем все опции смен
    const allShiftOptions = Array.from(shiftSelect.options).map(option => ({
        element: option,
        lineId: option.dataset.lineId,
        value: option.value,
        text: option.text
    }));

    // Функция для фильтрации смен
    function filterShifts() {
        const selectedLineId = lineSelect.value;
        shiftSelect.innerHTML = '<option value="">Все сутки</option>';

        // Если линия не выбрана, показываем все смены
        if (!selectedLineId) {
            allShiftOptions.forEach(shift => {
                if (shift.value) {
                    const option = document.createElement('option');
                    option.value = shift.value;
                    option.textContent = shift.text;
                    option.dataset.lineId = shift.lineId;
                    shiftSelect.appendChild(option);
                }
            });
            return;
        }

        // Фильтруем смены для выбранной линии
        const filteredShifts = allShiftOptions.filter(shift => shift.lineId === selectedLineId);

        filteredShifts.forEach(shift => {
            const option = document.createElement('option');
            option.value = shift.value;
            option.textContent = shift.text;
            option.dataset.lineId = shift.lineId;
            shiftSelect.appendChild(option);
        });
    }

    // Добавляем обработчик изменения линии
    lineSelect.addEventListener('change', filterShifts);

    // Запускаем фильтрацию при загрузке страницы
    filterShifts();
}); 