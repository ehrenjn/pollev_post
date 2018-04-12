# pollev_post
A python module for voting on multiple choice and free text polls on pollev.com  
Votes are always anonomous even if the poll requires a username  
  
Examples of usage:  
  
  
Voting for the first option on a multiple choice poll hosted at pollev.com/example_username:  
`cast_vote('example_username', 0)`  

Voting the word "test" on a text poll hosted at pollev.com/example_username:  
`cast_vote('example_username', 'test')`  

When voting on a text poll the second parameter will always be converted to a string, ie:  
`cast_vote('example_username', 0)`  
Votes for the string "0"
