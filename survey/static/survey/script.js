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

    handleDeletion(event) {
      console.log("Renumbering questions...");
      if (this.question_count_position > 0) {
        this.question_count_position--;
        this.decrementTotalForms();
      }

      setTimeout(() => {
        // Get all the *remaining* question cards
        const remainingQuestions = document.querySelectorAll(".question-card");
        // Loop through and re-number them
        remainingQuestions.forEach((question, index) => {
          const numberSpan = question.querySelector(".question-number");
          if (numberSpan) numberSpan.innerText = `${index + 1}.`;
        });
        // console.log(allQuestions);
      }, 500); // A timeout of 0 is all that's needed.
    },
  }));
});
