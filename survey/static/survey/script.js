document.addEventListener("alpine:init", () => {
  // Alpine.data() registers a reusable component.
  Alpine.data("optionsManager", (formPrefix, initialOptions = []) => ({
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
        `input[type=hidden][name="${formPrefix}-options"]`
      );
      console.log(" this.hiddenInput", this.hiddenInput);

      // 2. Set up the permanent "spy" on the options array.
      this.$watch("options", () => {
        // This function will now run AUTOMATICALLY whenever options change.
        console.log(" this.hiddenInput whach changed", this.hiddenInput);
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
  }));

  Alpine.data("questionManager", () => ({
    isDragging: false,
    question_count: 0,
    question_count_position: 0,
    questionID: null,

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

      totalFormsInput.value =
        totalFormsInput.value == "NaN"
          ? 0
          : parseInt(totalFormsInput.value) + delta;
      console.log("totalFormsInput.value", totalFormsInput.value);
    },

    incrementTotalForms() {
      this._updateTotalForms(1);
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
