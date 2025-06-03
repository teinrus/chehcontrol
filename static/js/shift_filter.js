document.addEventListener('DOMContentLoaded', function () {
    const lineSelect = document.getElementById('id_line');
    const shiftSelect = document.getElementById('id_shift');
    const dateInput = document.getElementById('id_date');

    if (!lineSelect || !shiftSelect || !dateInput) {
        return;
    }

    // Сохраняем все опции смен
    const allShiftOptions = Array.from(shiftSelect.options).map(option => ({
        element: option,
        lineId: option.dataset.lineId,
        value: option.value,
        text: option.text
    }));

    // Восстанавливаем сохранённые значения
    const savedLine = localStorage.getItem('selectedLine');
    const savedShift = localStorage.getItem('selectedShift');
    const savedDate = localStorage.getItem('selectedDate');

    if (savedLine) {
        lineSelect.value = savedLine;
    }

    if (savedDate) {
        dateInput.value = savedDate;
    }

    function filterShifts() {
        const selectedLineId = lineSelect.value;
        shiftSelect.innerHTML = '<option value="">Все сутки</option>';

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
        } else {
            const filteredShifts = allShiftOptions.filter(shift => shift.lineId === selectedLineId);
            filteredShifts.forEach(shift => {
                const option = document.createElement('option');
                option.value = shift.value;
                option.textContent = shift.text;
                option.dataset.lineId = shift.lineId;
                shiftSelect.appendChild(option);
            });
        }

        // Устанавливаем сохранённую смену, если она подходит
        if (savedShift) {
            const found = Array.from(shiftSelect.options).find(option => option.value === savedShift);
            if (found) {
                shiftSelect.value = savedShift;
            }
        }
    }

    // Сохраняем значения при изменении
    lineSelect.addEventListener('change', function () {
        localStorage.setItem('selectedLine', lineSelect.value);
        filterShifts();
        localStorage.setItem('selectedShift', ''); // сброс shift при смене линии
    });

    shiftSelect.addEventListener('change', function () {
        localStorage.setItem('selectedShift', shiftSelect.value);
    });

    dateInput.addEventListener('change', function () {
        localStorage.setItem('selectedDate', dateInput.value);
    });

    filterShifts(); // Запуск при загрузке
}); 