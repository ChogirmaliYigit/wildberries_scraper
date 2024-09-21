document.addEventListener("DOMContentLoaded", function () {
    // Inject modal HTML into the page
    const modalHTML = `
    <div class="modal-overlay" id="rejectModal" style="display: none;">
        <div class="modal-content">
            <div class="modal-body">
                <label for="reason" class="block text-sm font-medium text-gray-700 dark:text-gray-300">Причина:</label>
                <input
                class="border bg-white font-medium rounded-md shadow-sm text-gray-500 text-sm focus:ring focus:ring-primary-300 focus:border-primary-600 focus:outline-none group-[.errors]:border-red-600 group-[.errors]:focus:ring-red-200 dark:bg-gray-900 dark:border-gray-700 dark:text-gray-400 dark:focus:border-primary-600 dark:focus:ring-primary-700 dark:focus:ring-opacity-50 dark:group-[.errors]:border-red-500 dark:group-[.errors]:focus:ring-red-600/40 px-3 py-2 w-full max-w-2xl"
                type="text"
                name="reason"
                id="reason"
                placeholder="Введите причину"
                required>
                <div class="d-grid gap-2 mx-auto mt-4">
                    <button id="rejectSubmit" class="btn dark:bg-gray-900">Отклонить</button>
                </div>
            </div>
        </div>
    </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Modal handling logic
    const modal = document.getElementById('rejectModal');

    window.showRejectModal = function (commentId, rejectUrl) {
        modal.style.display = 'flex';

        // Handle submit action
        document.getElementById('rejectSubmit').onclick = function () {
            const reasonInput = document.querySelector('input[name="reason"]');
            if (reasonInput.value.trim() === "") {
                alert("Требуется причина.");
                return;
            }

            const reason = reasonInput.value;
            sendRejectRequest(commentId, rejectUrl, reason);
        };
    };

    // Close modal when clicking outside the modal content
    window.onclick = function(event) {
        if (event.target === modal) {
            modal.style.display = 'none';
        }
    };

    function sendRejectRequest(commentId, rejectUrl, reason) {
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        fetch(rejectUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': csrftoken
            },
            body: `reason=${encodeURIComponent(reason)}`
        })
        .then(response => {
            if (response.ok) {
                location.reload();  // Reload the page after rejection
            } else {
                alert('An error occurred');
            }
        });
    }
});
