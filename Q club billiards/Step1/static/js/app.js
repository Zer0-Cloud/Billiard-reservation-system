const bookingDate = document.querySelector("#booking-date");
const bookingTime = document.querySelector("#booking-time");
const bookingDuration = document.querySelector("#booking-duration");

if (bookingDate) {
  const today = new Date();
  const offset = today.getTimezoneOffset();
  const localDate = new Date(today.getTime() - offset * 60 * 1000);
  bookingDate.min = localDate.toISOString().split("T")[0];
}

function timeToMinutes(value) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours === 0 ? 24 * 60 + minutes : hours * 60 + minutes;
}

function updateDurationOptions() {
  if (!bookingTime || !bookingDuration || !bookingTime.value) {
    return;
  }

  const closingMinutes = 24 * 60 + 30;
  const availableMinutes = closingMinutes - timeToMinutes(bookingTime.value);
  let firstEnabledOption = null;

  Array.from(bookingDuration.options).forEach((option) => {
    const durationMinutes = Number(option.dataset.minutes);
    option.disabled = durationMinutes > availableMinutes;
    if (!option.disabled && !firstEnabledOption) {
      firstEnabledOption = option;
    }
  });

  if (bookingDuration.selectedOptions[0]?.disabled && firstEnabledOption) {
    bookingDuration.value = firstEnabledOption.value;
  }
}

if (bookingTime && bookingDuration) {
  bookingTime.addEventListener("change", updateDurationOptions);
  updateDurationOptions();
}
