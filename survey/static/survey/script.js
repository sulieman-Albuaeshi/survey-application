document.addEventListener("alpine:init", () => {
  // Alpine.data() registers a reusable component.
  Alpine.data(
    "optionsManager",
    (questionPrefix, type, initialOptions = []) => ({
      // --- DATA ---
      // We can pass in initial options from the Django template.
      // If nothing is passed, it defaults to an empty array.
      options: initialOptions,
      newOption: "",
      hiddenInput: null,

      init() {
        // 1. Find the hidden input field that Django created.
        // The form prefix (e.g., 'multi-0') is passed in directly from the template.
        this.hiddenInput = this.$el.querySelector(
          `input[type=hidden][name="${questionPrefix}-${type}"]`
        );
        console.log(" this.hiddenInput", this.hiddenInput);

        // 2. Set up the permanent "spy" on the options array.
        this.$watch("options", () => {
          // This function will now run AUTOMATICALLY whenever options change.
          this.hiddenInput.value = JSON.stringify(this.options);
        });
      },

      swap(array, indexA, indexB) {
        if (array.length <= 1) return;
        if (indexA === indexB) return;
        if (indexA < 0 || indexA >= array.length) return;
        if (indexB < 0 || indexB >= array.length) return;
        [array[indexA], array[indexB]] = [array[indexB], array[indexA]];
      },

      addOption() {
        if (this.newOption.trim() === "") {
          return;
        }
        if (!this.options.includes(this.newOption.trim())) {
          this.options.push(this.newOption.trim());
        }
        this.newOption = ""; // Clear the input
      },

      removeOption(index) {
        this.options.splice(index, 1);
      },
    })
  );

  Alpine.data("questionManager", () => ({
    isDragging: false,
    question_count_position: 0,
    questionID: null,

    init() {
      // 1. FIND THE DJANGO MANAGEMENT FORM INPUT
      // This input holds the true number of forms currently on the page
      const totalFormsInput = document.querySelector(
        `#id_questions-TOTAL_FORMS`
      );
      if (totalFormsInput) {
        // 2. SYNC ALPINE STATE WITH DJANGO
        // If Django rendered 1 form with an error, this value is '1'.
        // So our next new question must be index '1'.
        this.question_count_position = parseInt(totalFormsInput.value) || 0;
      } else {
        console.error(
          "Critical Error: #id_questions-TOTAL_FORMS not found. Ensure {{ formset.management_form }} is in your HTML."
        );
      }
    },

    moveQuestion(btnElement, direction) {
      // 1. Find the card and its container
      const currentCard = btnElement.closest(".question-card");
      const container = document.getElementById("question_container"); // Ensure your main div has this ID

      if (!currentCard || !container) return;

      // 2. Find the sibling to swap with
      if (direction === -1) {
        // Move UP
        const prevCard = currentCard.previousElementSibling;
        // Check if prevCard exists and is actually a question card (not a hidden div)
        if (prevCard && prevCard.classList.contains("question-card")) {
          container.insertBefore(currentCard, prevCard);
          this.updateQuestionOrder();
        }
      } else {
        // Move DOWN
        const nextCard = currentCard.nextElementSibling;
        if (nextCard && nextCard.classList.contains("question-card")) {
          // To move down, we insert the *next* card before the *current* card
          container.insertBefore(nextCard, currentCard);
          this.updateQuestionOrder();
        }
      }
    },

    /**
     * Updates the hidden TOTAL_FORMS input for a given Django formset.
     * @param {number} delta - The amount to change the count by (+1 or -1).
     */
    _updateTotalForms(delta) {
      const totalFormsInput = document.querySelector(
        `#id_questions-TOTAL_FORMS`
      );
      if (!totalFormsInput) {
        console.error(`TOTAL_FORMS input not found `);
        return;
      }
      const currentVal = parseInt(totalFormsInput.value) || 0;
      const newVal = currentVal + delta;

      totalFormsInput.value = newVal;

      // Update internal position tracker if needed
      this.question_count_position = newVal;
      console.log("totalFormsInput.value", totalFormsInput.value);
    },

    incrementTotalForms() {
      // Small delay to ensure HTMX request fires with the OLD count
      // before we increment it for the NEXT one.
      setTimeout(() => {
        this._updateTotalForms(1);
      }, 100);
    },

    decrementTotalForms() {
      this._updateTotalForms(-1);
    },

    updateQuestionOrder() {
      const allQuestions = document.querySelectorAll(".question-card");

      allQuestions.forEach((card, index) => {
        // 1. Update Visual Number (e.g., "1.")
        const numberSpan = card.querySelector(".question-number");
        if (numberSpan) numberSpan.innerText = `${index + 1}.`;

        // 2. Update Hidden Position Input (Important for Backend!)
        // Finds input ending in '-position', e.g., name="questions-0-position"
        const positionInput = card.querySelector('input[name$="-position"]');
        if (positionInput) {
          positionInput.value = index + 1;
        }
      });
    },

    handleDeletion(event) {
      console.log("Renumbering questions...");
      if (this.question_count_position > 0) {
        this.question_count_position--;
        this.decrementTotalForms();
      }

      // Wait for DOM removal then reorder
      setTimeout(() => {
        this.updateQuestionOrder();
      }, 500);
    },
  }));
});
