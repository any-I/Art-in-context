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
    items: listItems,
    onSelectedItemChange: (changes) => {
      setSelectedValue(changes.selectedItem[itemKey]);
    },
    onInputValueChange: (changes) => {
      const inputValue = changes.inputValue;
      //main filtering function - as long as the option includes
      //the input value, include
      const newListItems = options.filter((option) => {
        const optValue = option[itemKey].toLowerCase();
        return optValue.includes(inputValue.toLowerCase());
      });
      setListItems(newListItems);
      //remember to update input value to the newly-typed one
      setSelectedValue(inputValue);
    },
    itemToString: (item) => {
      return (item && itemKey in item) ? item[itemKey]:"";
    }
  });

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
              {...getInputProps()}/>
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