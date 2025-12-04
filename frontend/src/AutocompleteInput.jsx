import * as React from 'react';
import {useCombobox} from 'downshift';

//mini-component to have a piece of text be formatted so the 
//first instance of `matchingStr` within it is bolded
const BoldedText = ({originalStr, matchingStr}) => {
  const matchStart = originalStr.toLowerCase().indexOf(matchingStr.toLowerCase());
  const matchEnd = matchStart + matchingStr.length;
  if(matchStart === -1){
    return (<span>{originalStr}</span>);
  }
  return (
  <span>
    {originalStr.substring(0, matchStart)}
    <span className="bold-text">{originalStr.substring(matchStart, matchEnd)}</span>
    {originalStr.substring(matchEnd)}
  </span>
  );
};

//combo box given list of objects, searchable by the given item key
const AutocompleteInput = ({
  options, 
  itemKey, 
  label, 
  placeholder, 
  selectedValue,
  setSelectedValue
}) => {
  const [listItems, setListItems] = React.useState(options);
  const [value, setValue] = React.useState("");
  const {
    isOpen,
    getToggleButtonProps,
    getLabelProps,
    getMenuProps,
    getInputProps,
    highlightedIndex,
    getItemProps,
    selectedItem
  } = useCombobox({
    inputValue: selectedValue,
    items: listItems,
    onSelectedItemChange: (changes) => {
      const newValue = changes.selectedItem[itemKey];
      setSelectedValue(newValue);
      setValue(newValue);
    },
    itemToString: (item) => {
      return (item && itemKey in item) ? item[itemKey]:"";
    }
  });

  //filter list to only those that contains the input value
  const filterItems = (value) => {
    const newListItems = options.filter((option) => {
      const optValue = option[itemKey].toLowerCase();
      return optValue.includes(value.toLowerCase());
    });
    setListItems(newListItems);
  }

  //main function handling an input change
  const onInputChange = (e) => {
    const inputValue = e.target.value;
    //update dropdown
    filterItems(inputValue);
    //remember to update input value to the newly-typed one
    if(selectedValue !== inputValue){
      setSelectedValue(inputValue);
    }
    setValue(inputValue);
  };
  
  //if selected value has changed, set value to selected value
  //necessary to update value if carousel has set the selected value to 
  //something else
  if(value !== selectedValue){
    setValue(selectedValue);
    filterItems(selectedValue);
  }

  return (
    <div className="combobox-cont">
      {/*dropdown label*/}
      <div className="combobox-label-cont">
        <label className="label-item" {...getLabelProps()}>
          {label}
        </label>
        <div className="combobox-input-cont">
          <input placeholder={placeholder}
              className="combobox-input form-control"
              {...getInputProps({
                onChange: onInputChange
              })}/>
          <button aria-label="toggle menu"
                  className={"combobox-arrow" + (isOpen ? " open":" closed")}
                  {...getToggleButtonProps()}>
            <span>{isOpen ? <>&#8593;</> : <>&#8595;</>}</span>
          </button>
        </div>
      </div>
      {/*dropdown options*/}
      {(isOpen && listItems.length > 0) &&
        (<ul className="combobox-dropdown"
          {...getMenuProps()}
        >
          {listItems.map((item, index) => (
            <li className={
                  "combobox-li" + 
                  (highlightedIndex === index ? " highlighted":"") +
                  (selectedItem && selectedValue === item[itemKey] ? " selected":"")
                }
                key={item[itemKey]}
                {...getItemProps({item, index})}
            >
              <BoldedText originalStr={item[itemKey]} 
                          matchingStr={selectedValue}>
              </BoldedText>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default AutocompleteInput;